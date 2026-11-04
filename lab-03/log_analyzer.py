#!/usr/bin/env python3
"""Аналізатор журналу веб-сервера у комбінованому форматі (Apache/nginx «combined»).

Формат рядка:
  IP ident user [день/міс/рік:год:хв:сек зона] "МЕТОД шлях ПРОТОКОЛ" код розмір "referer" "user-agent"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

EXIT_OK = 0
EXIT_USAGE = 2  # argparse використовує 2 для помилок параметрів
EXIT_INPUT = 3  # вхідний файл не існує / не читається
EXIT_OUTPUT = 4  # вихідний файл неможливо записати

LINE_RE = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] '
    r'"(?P<method>[A-Z]+) (?P<path>\S+) (?P<proto>[^"]+)" '
    r'(?P<status>\d{3}) (?P<size>\d+|-)'
    r'(?: "(?P<referer>[^"]*)" "(?P<agent>[^"]*)")?\s*$'
)
TIME_FMT = "%d/%b/%Y:%H:%M:%S %z"


@dataclass(frozen=True)
class Entry:
    ip: str
    time: datetime
    method: str
    path: str
    status: int
    size: int


def parse_line(line: str) -> Entry | None:
    """Розбирає один рядок. Повертає None для пошкодженого рядка — без винятків."""
    m = LINE_RE.match(line.rstrip("\r\n"))
    if not m:
        return None
    try:
        when = datetime.strptime(m["time"], TIME_FMT)
    except ValueError:
        return None
    status = int(m["status"])
    if not 100 <= status <= 599:
        return None
    return Entry(
        ip=m["ip"], time=when, method=m["method"], path=m["path"],
        status=status, size=0 if m["size"] == "-" else int(m["size"]),
    )


def analyze(lines, top: int) -> dict:
    total = bad = 0
    ips: Counter[str] = Counter()
    classes: Counter[str] = Counter()
    hours: Counter[int] = Counter()
    for line in lines:
        if not line.strip():
            continue
        total += 1
        entry = parse_line(line)
        if entry is None:
            bad += 1
            continue
        ips[entry.ip] += 1
        classes[f"{entry.status // 100}xx"] += 1
        hours[entry.time.hour] += 1

    parsed = total - bad
    peak = max(hours.values(), default=0)
    return {
        "lines_total": total,
        "lines_parsed": parsed,
        "lines_malformed": bad,
        "top_ips": [{"ip": ip, "requests": n} for ip, n in ips.most_common(top)],
        "status_classes": {k: classes.get(k, 0) for k in ("1xx", "2xx", "3xx", "4xx", "5xx")},
        "requests_by_hour": {f"{h:02d}": hours.get(h, 0) for h in range(24)},
        "peak_hours": [f"{h:02d}:00" for h, n in sorted(hours.items()) if n == peak and peak > 0],
    }


def render_text(r: dict, source: str) -> str:
    out = [f"Звіт за журналом: {source}",
           f"Рядків: {r['lines_total']}, розібрано: {r['lines_parsed']}, пошкоджених: {r['lines_malformed']}",
           "", f"Топ-{len(r['top_ips'])} адрес за кількістю запитів:"]
    width = max((len(x["ip"]) for x in r["top_ips"]), default=0)
    out += [f"  {i:>2}. {x['ip']:<{width}}  {x['requests']}" for i, x in enumerate(r["top_ips"], 1)]
    out += ["", "Коди відповіді за класами:"]
    parsed = r["lines_parsed"] or 1
    out += [f"  {k}: {v:>6}  ({v * 100 / parsed:5.1f}%)" for k, v in r["status_classes"].items()]
    out += ["", "Запити за годинами (пік позначено ◄):"]
    peak = max(r["requests_by_hour"].values(), default=0) or 1
    for h, n in r["requests_by_hour"].items():
        bar = "█" * round(n * 30 / peak)
        mark = " ◄ пік" if f"{h}:00" in r["peak_hours"] else ""
        out.append(f"  {h}:00 {n:>5} {bar}{mark}")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="log_analyzer.py",
        description="Звіт за журналом веб-сервера (combined): топ адрес, класи кодів відповіді, "
        "години пікового навантаження. Пошкоджені рядки не зупиняють розбір — їх кількість є у звіті.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
коди виходу:
  0  звіт побудовано
  2  неправильні параметри
  3  вхідний файл не існує або не читається
  4  неможливо записати вихідний файл

приклад:
  python log_analyzer.py --input samples/access.log --top 5
  python log_analyzer.py -i samples/access.log -o report.json --format json""",
    )
    p.add_argument("-i", "--input", type=Path, required=True, help="журнал у форматі combined")
    p.add_argument("-o", "--output", type=Path, help="куди записати звіт (типово — stdout)")
    p.add_argument("-f", "--format", choices=("text", "json"), default="text", help="формат звіту (типово: text)")
    p.add_argument("-n", "--top", type=int, default=10, help="кількість адрес у топі (типово: 10)")
    args = p.parse_args(argv)
    if args.top < 1:
        p.error("--top має бути >= 1")

    try:
        # errors="replace": байти не в UTF-8 не валять розбір, а роблять рядок «пошкодженим»
        with args.input.open(encoding="utf-8", errors="replace") as f:
            report = analyze(f, args.top)
    except OSError as e:
        print(f"log_analyzer.py: не вдалося прочитати {args.input}: {e.strerror}", file=sys.stderr)
        return EXIT_INPUT

    text = (json.dumps(report, ensure_ascii=False, indent=2) + "\n" if args.format == "json"
            else render_text(report, str(args.input)))
    if args.output:
        try:
            args.output.write_text(text, encoding="utf-8")
        except OSError as e:
            print(f"log_analyzer.py: не вдалося записати {args.output}: {e.strerror}", file=sys.stderr)
            return EXIT_OUTPUT
        print(f"звіт записано: {args.output} ({report['lines_parsed']} рядків, "
              f"пошкоджених: {report['lines_malformed']})", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
