#!/usr/bin/env bash
# backup.sh — стиснений архів теки з ротацією старих копій.
set -euo pipefail

readonly SCRIPT_NAME="${0##*/}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
LOG_FILE="${BACKUP_LOG:-$SCRIPT_DIR/logs/backup.log}"

# Коди виходу: різні причини — різні коди.
readonly E_USAGE=1     # неправильні або відсутні параметри
readonly E_SOURCE=2    # джерело не існує або недоступне для читання
readonly E_DEST=3      # теку призначення неможливо створити / записати
readonly E_ARCHIVE=4   # tar завершився з помилкою
readonly E_ROTATE=5    # не вдалося видалити старий архів

usage() {
  cat <<EOF
Використання: $SCRIPT_NAME --source <шлях> --dest <шлях> [--keep N] [--dry-run]

Створює архів <ім'я-джерела>-РРРР-ММ-ДД-ГГХХСС.tar.gz у теці призначення
й залишає лише N найновіших архівів ЦЬОГО джерела (чужі файли не чіпає).

Параметри:
  --source <шлях>  тека, яку архівуємо (обов'язковий)
  --dest <шлях>    куди складати архіви; створюється, якщо немає (обов'язковий)
  --keep <N>       скільки останніх копій зберігати, ціле >= 1 (типово 5)
  --dry-run        показати всі дії, нічого не створюючи й не видаляючи
  -h, --help       ця довідка

Журнал: $LOG_FILE (змінна BACKUP_LOG змінює шлях)

Коди виходу:
  0  успіх
  1  неправильні параметри
  2  джерело не існує або недоступне
  3  тека призначення недоступна
  4  помилка архівування
  5  помилка видалення старих копій

Приклад:
  $SCRIPT_NAME --source ~/projects/app --dest /mnt/backup --keep 3
  $SCRIPT_NAME --source "./my project" --dest ./backups --dry-run
EOF
}

log() {
  # Кожен рядок самодостатній: час, дія, результат.
  local line
  line="$(date '+%Y-%m-%dT%H:%M:%S%z') action=$1 result=$2${3:+ $3}"
  if [[ "$DRY_RUN" == true ]]; then
    line="$line dry_run=true"
  fi
  mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
  printf '%s\n' "$line" >> "$LOG_FILE" 2>/dev/null || printf 'попередження: не вдалося записати журнал %s\n' "$LOG_FILE" >&2
}

die() {
  # die <код> <повідомлення> — зрозуміле повідомлення в stderr, запис у журнал, вихід.
  local code=$1; shift
  printf '%s: помилка: %s\n' "$SCRIPT_NAME" "$*" >&2
  log backup failed "code=$code reason=\"$*\""
  exit "$code"
}

say() { printf '%s\n' "$*"; }

# ---------- розбір параметрів ----------
SOURCE="" DEST="" KEEP=5 DRY_RUN=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --source) [[ $# -ge 2 ]] || die $E_USAGE "--source потребує значення"; SOURCE=$2; shift 2 ;;
    --dest)   [[ $# -ge 2 ]] || die $E_USAGE "--dest потребує значення";   DEST=$2;   shift 2 ;;
    --keep)   [[ $# -ge 2 ]] || die $E_USAGE "--keep потребує значення";   KEEP=$2;   shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf '%s: невідомий параметр: %s\n\n' "$SCRIPT_NAME" "$1" >&2; usage >&2; exit $E_USAGE ;;
  esac
done

[[ -n "$SOURCE" ]] || { printf '%s: не вказано --source\n' "$SCRIPT_NAME" >&2; usage >&2; exit $E_USAGE; }
[[ -n "$DEST" ]]   || { printf '%s: не вказано --dest\n' "$SCRIPT_NAME" >&2; usage >&2; exit $E_USAGE; }
[[ "$KEEP" =~ ^[1-9][0-9]*$ ]] || die $E_USAGE "--keep має бути цілим числом >= 1, отримано: '$KEEP'"

# ---------- 1. джерело ----------
SOURCE=${SOURCE%/}
[[ -e "$SOURCE" ]] || die $E_SOURCE "джерело не існує: $SOURCE"
[[ -d "$SOURCE" ]] || die $E_SOURCE "джерело не є текою: $SOURCE"
[[ -r "$SOURCE" && -x "$SOURCE" ]] || die $E_SOURCE "немає прав на читання джерела: $SOURCE"

SRC_PARENT=$(cd "$SOURCE/.." && pwd)
SRC_NAME=$(basename "$(cd "$SOURCE" && pwd)")

# ---------- 2. призначення ----------
if [[ ! -d "$DEST" ]]; then
  if [[ "$DRY_RUN" == true ]]; then
    say "[dry-run] створити теку призначення: $DEST"
  else
    mkdir -p "$DEST" || die $E_DEST "не вдалося створити теку призначення: $DEST"
    say "створено теку призначення: $DEST"
  fi
fi
if [[ -d "$DEST" && ! -w "$DEST" ]]; then
  die $E_DEST "немає прав на запис у теку призначення: $DEST"
fi

# ---------- 3. архів ----------
# Мітка РРРР-ММ-ДД-ГГХХСС: лексикографічне сортування імен = хронологічне.
stamp() { date '+%Y-%m-%d-%H%M%S'; }
TS=$(stamp)
ARCHIVE="$DEST/$SRC_NAME-$TS.tar.gz"
# Два запуски в одну секунду дали б однакове ім'я й перезаписали архів — чекаємо наступну секунду.
while [[ -e "$ARCHIVE" ]]; do
  sleep 1
  TS=$(stamp)
  ARCHIVE="$DEST/$SRC_NAME-$TS.tar.gz"
done

FILES_COUNT=$(find "$SOURCE" -type f | wc -l | tr -d ' ')

if [[ "$DRY_RUN" == true ]]; then
  say "[dry-run] створити архів: $ARCHIVE ($FILES_COUNT файлів із $SOURCE)"
  ARCHIVE_SIZE=0
else
  TMP="$ARCHIVE.part"
  # Пишемо у тимчасовий файл і перейменовуємо: обірваний архів ніколи не виглядає як готовий.
  # Архів пишемо в stdout і перенаправляємо у файл: GNU tar сприймає «C:\…» у -f як
  # віддалений хост (синтаксис host:path), а перенаправлення працює однаково скрізь.
  if ! tar -czf - -C "$SRC_PARENT" "$SRC_NAME" > "$TMP"; then
    rm -f "$TMP"
    die $E_ARCHIVE "tar не зміг створити архів із $SOURCE"
  fi
  mv "$TMP" "$ARCHIVE"
  ARCHIVE_SIZE=$(wc -c < "$ARCHIVE" | tr -d ' ')
  say "створено архів: $ARCHIVE ($FILES_COUNT файлів, $ARCHIVE_SIZE байт)"
fi

# ---------- 4. ротація ----------
# Лише архіви ЦЬОГО джерела: ім'я + точний формат мітки. Лапки навколо змінних —
# щоб пробіли й символи глобу в імені сприймались буквально.
shopt -s nullglob
existing=( "$DEST/$SRC_NAME"-[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9].tar.gz )
shopt -u nullglob

# У dry-run нового архіву ще немає, але рахувати треба так, ніби він є.
if [[ "$DRY_RUN" == true ]]; then
  existing+=( "$ARCHIVE" )
fi

# Глоб повертає імена відсортованими; мітка в імені робить цей порядок хронологічним.
DELETED=0
excess=$(( ${#existing[@]} - KEEP ))
if (( excess > 0 )); then
  for old in "${existing[@]:0:excess}"; do
    if [[ "$DRY_RUN" == true ]]; then
      say "[dry-run] видалити старий архів: $old"
    else
      rm -f -- "$old" || die $E_ROTATE "не вдалося видалити $old"
      say "видалено старий архів: $old"
    fi
    DELETED=$((DELETED + 1))
  done
fi

KEPT=$(( ${#existing[@]} - DELETED ))
say "залишено архівів $SRC_NAME: $KEPT (--keep $KEEP)"

# ---------- 5. журнал ----------
log backup ok "source=\"$SOURCE\" archive=\"$ARCHIVE\" files=$FILES_COUNT size_bytes=$ARCHIVE_SIZE deleted=$DELETED kept=$KEPT"
