#!/usr/bin/env bash
# fsort.sh — скриптовий аналог go/fsort для порівняння розміру й часу запуску.
#   fsort.sh sort [--dry-run] <тека>
#   fsort.sh stats <тека>
set -euo pipefail

category() {
  local ext="${1##*.}"
  [[ "$1" == *.* ]] || { echo other; return; }
  case "${ext,,}" in
    pdf|doc|docx|odt|txt|md|rtf|xls|xlsx|ppt|pptx|csv) echo documents ;;
    jpg|jpeg|png|gif|bmp|svg|webp|heic|tiff)           echo images ;;
    mp4|mkv|avi|mov|webm|wmv|flv)                      echo video ;;
    zip|tar|gz|tgz|bz2|xz|7z|rar)                      echo archives ;;
    *)                                                 echo other ;;
  esac
}

usage() { echo "Використання: ${0##*/} sort [--dry-run] <тека> | stats <тека>"; }

cmd=${1:-}; shift || true
case "$cmd" in
  sort)
    dry=false
    [[ "${1:-}" == --dry-run ]] && { dry=true; shift; }
    dir=${1:?$(usage)}
    [[ -d "$dir" ]] || { echo "тека не існує: $dir" >&2; exit 2; }
    n=0
    for f in "$dir"/*; do
      [[ -f "$f" ]] || continue
      c=$(category "${f##*/}")
      if $dry; then echo "[dry-run] ${f##*/} -> $dir/$c/"; else mkdir -p "$dir/$c" && mv -n -- "$f" "$dir/$c/"; fi
      n=$((n + 1))
    done
    echo "розкладено: $n"
    ;;
  stats)
    dir=${1:?$(usage)}
    [[ -d "$dir" ]] || { echo "тека не існує: $dir" >&2; exit 2; }
    declare -A cnt=()
    for f in "$dir"/*; do [[ -f "$f" ]] && cnt[$(category "${f##*/}")]=$(( ${cnt[$(category "${f##*/}")]:-0} + 1 )); done
    for c in documents images video archives other; do printf '%-10s %d\n' "$c" "${cnt[$c]:-0}"; done
    ;;
  -h|--help|help) usage ;;
  *) usage >&2; exit 2 ;;
esac
