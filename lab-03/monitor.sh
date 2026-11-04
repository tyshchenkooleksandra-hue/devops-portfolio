#!/usr/bin/env bash
# monitor.sh — перевірка стану машини з порогами (Linux: читає /proc).
set -euo pipefail

SCRIPT_NAME="${0##*/}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_NAME SCRIPT_DIR

readonly E_ALERT=1     # перевищено поріг або процес не працює
readonly E_CONFIG=2    # неправильні параметри / конфігурація
readonly E_PLATFORM=3  # немає /proc — не Linux

usage() {
  cat <<EOF
Використання: $SCRIPT_NAME [--config <файл>]

Перевіряє процесор, пам'ять, вільне місце на дисках і задані процеси.
Кожен рядок виводу самодостатній (час, хост, показник, значення, поріг, статус) —
придатний для cron і журналів. Інтерактивних елементів немає.

Пороги (змінні середовища мають пріоритет над файлом конфігурації):
  MON_CPU_MAX      макс. завантаження CPU, %          (типово 90)
  MON_MEM_MAX      макс. використання пам'яті, %       (типово 90)
  MON_DISK_MAX     макс. заповнення диска, %           (типово 90)
  MON_DISK_PATHS   точки монтування через пробіл       (типово "/")
  MON_PROCESSES    імена процесів через пробіл         (типово порожньо)
  MON_LOG          файл журналу      (типово $SCRIPT_DIR/logs/monitor.log)

Параметри:
  --config <файл>  KEY=VALUE з порогами (типово $SCRIPT_DIR/config/monitor.conf)
  -h, --help       ця довідка

Коди виходу: 0 — усе в нормі, 1 — є перевищення, 2 — помилка конфігурації, 3 — не Linux.

Приклад:
  MON_CPU_MAX=1 $SCRIPT_NAME                       # штучно занижений поріг — спрацює
  $SCRIPT_NAME --config config/monitor.conf
EOF
}

die() { printf '%s: помилка: %s\n' "$SCRIPT_NAME" "$2" >&2; exit "$1"; }

CONFIG="$SCRIPT_DIR/config/monitor.conf"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) [[ $# -ge 2 ]] || die $E_CONFIG "--config потребує значення"; CONFIG=$2; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die $E_CONFIG "невідомий параметр: $1 (див. --help)" ;;
  esac
done

[[ -r /proc/stat && -r /proc/meminfo ]] || die $E_PLATFORM "немає /proc — скрипт працює лише в Linux (на Windows — у WSL)"

# Конфіг читаємо як дані, а не через `source`: файл із порогами не повинен мати змоги виконати код.
declare -A CONF=()
if [[ -f "$CONFIG" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    line=${line%%#*}
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    [[ "$line" =~ ^[[:space:]]*(MON_[A-Z_]+)[[:space:]]*=[[:space:]]*\"?([^\"]*)\"?[[:space:]]*$ ]] \
      || die $E_CONFIG "$CONFIG: незрозумілий рядок: $line"
    CONF[${BASH_REMATCH[1]}]=${BASH_REMATCH[2]}
  done < "$CONFIG"
elif [[ "$CONFIG" != "$SCRIPT_DIR/config/monitor.conf" ]]; then
  die $E_CONFIG "файл конфігурації не знайдено: $CONFIG"
fi

setting() {  # setting <ІМ'Я> <типово>: змінна середовища → конфіг → типове значення
  local name=$1 def=$2
  if [[ -n "${!name:-}" ]]; then printf '%s' "${!name}"
  elif [[ -n "${CONF[$name]:-}" ]]; then printf '%s' "${CONF[$name]}"
  else printf '%s' "$def"; fi
}

CPU_MAX=$(setting MON_CPU_MAX 90)
MEM_MAX=$(setting MON_MEM_MAX 90)
DISK_MAX=$(setting MON_DISK_MAX 90)
DISK_PATHS=$(setting MON_DISK_PATHS "/")
PROCESSES=$(setting MON_PROCESSES "")
LOG_FILE=$(setting MON_LOG "$SCRIPT_DIR/logs/monitor.log")
for v in CPU_MAX MEM_MAX DISK_MAX; do
  if ! [[ "${!v}" =~ ^[0-9]+$ ]] || (( ${!v} > 100 )); then
    die $E_CONFIG "MON_$v має бути цілим 0–100, отримано '${!v}'"
  fi
done

mkdir -p "$(dirname "$LOG_FILE")"
HOST=$(hostname)
ALERTS=0

report() {  # report <показник> <значення> <поріг> <статус> [деталі]
  local line
  line="$(date '+%Y-%m-%dT%H:%M:%S%z') host=$HOST check=$1 value=$2 threshold=$3 status=$4${5:+ $5}"
  printf '%s\n' "$line"
  printf '%s\n' "$line" >> "$LOG_FILE"
  [[ "$4" == OK ]] || ALERTS=$((ALERTS + 1))
}

# --- CPU: дві вибірки /proc/stat з інтервалом 1 с; завантаження = 1 − Δidle/Δtotal.
read_cpu() { local _ u n s i w q sq st; read -r _ u n s i w q sq st _ < /proc/stat; echo "$((u+n+s+i+w+q+sq+st)) $((i+w))"; }
read -r t1 i1 < <(read_cpu); sleep 1; read -r t2 i2 < <(read_cpu)
dt=$((t2 - t1)); di=$((i2 - i1))
cpu=$(( dt > 0 ? (100 * (dt - di)) / dt : 0 ))
report cpu "${cpu}%" "${CPU_MAX}%" "$( (( cpu > CPU_MAX )) && echo ALERT || echo OK )"

# --- Пам'ять: MemAvailable, а не MemFree — кеш файлової системи ядро віддасть за потреби.
mem_total=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
mem_avail=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
mem=$(( 100 * (mem_total - mem_avail) / mem_total ))
report memory "${mem}%" "${MEM_MAX}%" "$( (( mem > MEM_MAX )) && echo ALERT || echo OK )" "available_mb=$((mem_avail / 1024))"

# --- Диски.
for mnt in $DISK_PATHS; do
  if ! usage_line=$(df -P "$mnt" 2>/dev/null | awk 'NR==2 {print $5, $4}'); then
    report "disk:$mnt" "n/a" "${DISK_MAX}%" ALERT "reason=недоступна_точка_монтування"
    continue
  fi
  read -r used_pct free_kb <<< "$usage_line"
  used=${used_pct%\%}
  report "disk:$mnt" "${used}%" "${DISK_MAX}%" "$( (( used > DISK_MAX )) && echo ALERT || echo OK )" "free_gb=$((free_kb / 1024 / 1024))"
done

# --- Процеси.
for p in $PROCESSES; do
  if pids=$(pgrep -x "$p"); then
    report "process:$p" "running" "running" OK "pids=$(echo "$pids" | paste -sd, -)"
  else
    report "process:$p" "stopped" "running" ALERT
  fi
done

if (( ALERTS > 0 )); then
  exit $E_ALERT
fi
