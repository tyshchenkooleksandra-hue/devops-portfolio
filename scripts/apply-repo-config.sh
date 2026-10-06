#!/usr/bin/env bash
# Застосовує налаштування з repo-config/ до репозиторію GitHub однією командою.
#
#   scripts/apply-repo-config.sh <owner>/<repo> [--create] [--no-project]
#
#   --create      створити новий порожній публічний репозиторій перед налаштуванням
#   --no-project  не створювати дошку Projects і задачі
#
# Потрібно: gh, авторизований зі scope `repo` і `project`
#   gh auth refresh -s project
#
# Скрипт ідемпотентний: повторний запуск оновлює ruleset, а не дублює його.
set -euo pipefail

usage() { sed -n '2,12p' "$0"; exit 1; }
[[ $# -ge 1 ]] || usage

REPO="$1"; shift
CREATE=false; WITH_PROJECT=true
for arg in "$@"; do
  case "$arg" in
    --create) CREATE=true ;;
    --no-project) WITH_PROJECT=false ;;
    *) usage ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CFG="$ROOT/repo-config"
OWNER="${REPO%%/*}"
log() { printf '\n==> %s\n' "$*"; }

# --- 1. Репозиторій ---------------------------------------------------------
if $CREATE; then
  log "Створюю публічний репозиторій $REPO"
  gh repo create "$REPO" --public --description "Тестовий репозиторій для перевірки правил як коду"
fi

log "Загальні налаштування репозиторію (repository.json)"
gh api -X PATCH "repos/$REPO" --input "$CFG/repository.json" --silent

# --- 2. Початковий вміст ----------------------------------------------------
# Ruleset забороняє прямі зміни в main, тому шаблон PR і перший коміт
# мають потрапити в репозиторій ДО увімкнення правил.
put_file() {
  local src="$1" dst="$2" msg="$3"
  # при 404 gh api друкує тіло помилки в stdout, тому дивимось лише на код виходу
  if gh api "repos/$REPO/contents/$dst" --silent 2>/dev/null; then
    echo "  $dst вже існує — пропускаю"
    return
  fi
  gh api -X PUT "repos/$REPO/contents/$dst" \
    -f message="$msg" \
    -f content="$(base64 -w0 < "$src")" --silent
  echo "  + $dst"
}

log "Шаблон pull request і базові файли"
put_file "$ROOT/.github/pull_request_template.md" ".github/pull_request_template.md" "chore: add pull request template"
put_file "$ROOT/.editorconfig" ".editorconfig" "chore: add .editorconfig"

# --- 3. Ruleset для main ----------------------------------------------------
RULESET_NAME="$(sed -n 's/.*"name": *"\([^"]*\)".*/\1/p' "$CFG/ruleset-main.json" | head -1)"
log "Ruleset '$RULESET_NAME' (ruleset-main.json)"
RULESET_ID="$(gh api "repos/$REPO/rulesets" --jq ".[] | select(.name == \"$RULESET_NAME\") | .id")"
if [[ -n "$RULESET_ID" ]]; then
  gh api -X PUT "repos/$REPO/rulesets/$RULESET_ID" --input "$CFG/ruleset-main.json" --silent
  echo "  оновлено ruleset #$RULESET_ID"
else
  gh api -X POST "repos/$REPO/rulesets" --input "$CFG/ruleset-main.json" --jq '"  створено ruleset #\(.id)"'
fi

# --- 4. Дошка проєкту -------------------------------------------------------
if $WITH_PROJECT; then
  # shellcheck source=/dev/null
  source "$CFG/project.conf"

  PROJECT_NUM="$(gh project list --owner "$OWNER" --format json --limit 100 \
    --jq ".projects[] | select(.title == \"$PROJECT_TITLE ($REPO)\") | .number")"

  if [[ -n "$PROJECT_NUM" ]]; then
    log "Дошка '$PROJECT_TITLE ($REPO)' вже існує (#$PROJECT_NUM)"
  elif [[ -n "${PROJECT_TEMPLATE:-}" ]]; then
    log "Копіюю дошку з шаблону $PROJECT_TEMPLATE (разом з автоматизаціями)"
    tpl_owner="${PROJECT_TEMPLATE%%/*}"; tpl_num="${PROJECT_TEMPLATE##*/}"
    PROJECT_NUM="$(gh project copy "$tpl_num" --source-owner "$tpl_owner" --target-owner "$OWNER" \
      --title "$PROJECT_TITLE ($REPO)" --format json --jq .number)"
  else
    log "Створюю дошку '$PROJECT_TITLE ($REPO)'"
    PROJECT_NUM="$(gh project create --owner "$OWNER" --title "$PROJECT_TITLE ($REPO)" --format json --jq .number)"

    # Колонки дошки — це варіанти поля Status. Замінюємо стандартні
    # Todo / In Progress / Done на наші.
    FIELD_ID="$(gh project field-list "$PROJECT_NUM" --owner "$OWNER" --format json \
      --jq '.fields[] | select(.name == "Status") | .id')"
    opts=""
    for o in "${STATUS_OPTIONS[@]}"; do
      opts+="${opts:+,}{name:\"$o\",color:GRAY,description:\"\"}"
    done
    gh api graphql --silent -f query="
      mutation {
        updateProjectV2Field(input: {fieldId: \"$FIELD_ID\", singleSelectOptions: [$opts]}) {
          projectV2Field { ... on ProjectV2SingleSelectField { name } }
        }
      }"
    echo "  колонки: ${STATUS_OPTIONS[*]}"
  fi

  gh project link "$PROJECT_NUM" --owner "$OWNER" --repo "$REPO"

  # Ідентифікатори для явного виставлення статусу першої колонки (Backlog)
  PROJECT_ID="$(gh project view "$PROJECT_NUM" --owner "$OWNER" --format json --jq .id)"
  FIELD_ID="$(gh project field-list "$PROJECT_NUM" --owner "$OWNER" --format json \
    --jq '.fields[] | select(.name == "Status") | .id')"
  BACKLOG_ID="$(gh project field-list "$PROJECT_NUM" --owner "$OWNER" --format json \
    --jq ".fields[] | select(.name == \"Status\") | .options[] | select(.name == \"${STATUS_OPTIONS[0]}\") | .id")"

  log "Задачі на кожен модуль і фінальний проєкт (issues.tsv)"
  while IFS=$'\t' read -r title body; do
    [[ -z "$title" ]] && continue
    if gh issue list --repo "$REPO" --state all --search "in:title \"$title\"" --json title \
        --jq ".[] | select(.title == \"$title\") | .title" | grep -q .; then
      echo "  = $title (вже існує)"
      continue
    fi
    url="$(gh issue create --repo "$REPO" --title "$title" --body "$body")"
    item="$(gh project item-add "$PROJECT_NUM" --owner "$OWNER" --url "$url" --format json --jq .id)"
    gh project item-edit --project-id "$PROJECT_ID" --id "$item" \
      --field-id "$FIELD_ID" --single-select-option-id "$BACKLOG_ID" >/dev/null
    echo "  + $url → ${STATUS_OPTIONS[0]}"
  done < "$CFG/issues.tsv"

  cat <<EOF

  Дошка: https://github.com/users/$OWNER/projects/$PROJECT_NUM
  УВАГА: API GitHub не дозволяє вмикати вбудовані workflows дошки.
  Їх переносить лише копіювання з шаблону (PROJECT_TEMPLATE у project.conf).
EOF
fi

log "Готово: https://github.com/$REPO"
gh api "repos/$REPO/rulesets" --jq '.[] | "  ruleset: \(.name) [\(.enforcement)]"'
