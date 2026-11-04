#!/usr/bin/env python3
"""Генерує тестовий журнал access.log у форматі combined (детерміновано, seed=42).

Навантаження нерівномірне за годинами (пік — вечір), кілька «гарячих» адрес,
і навмисно пошкоджені рядки, щоб перевірити стійкість аналізатора.
"""

import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

random.seed(42)
OUT = Path(__file__).with_name("access.log")
TZ = timezone(timedelta(hours=2))
START = datetime(2026, 10, 1, tzinfo=TZ)

IPS = [f"203.0.113.{i}" for i in range(1, 40)] + [f"198.51.100.{i}" for i in range(1, 20)]
HOT = ["203.0.113.7", "198.51.100.3", "203.0.113.21"]
PATHS = ["/", "/api/v1/items", "/api/v1/items/42", "/login", "/static/app.js", "/static/style.css", "/health"]
STATUSES = [200] * 70 + [201] * 3 + [301, 302, 304] * 4 + [400, 401, 403] + [404] * 6 + [500, 502, 503]
AGENTS = ['Mozilla/5.0 (X11; Linux x86_64)', 'curl/8.19.0', 'python-requests/2.33']
# ваги годин: нічний мінімум, ранковий підйом, вечірній пік о 20–21
HOUR_WEIGHTS = [2, 1, 1, 1, 1, 2, 4, 7, 10, 12, 12, 11, 12, 12, 11, 10, 11, 13, 16, 19, 24, 24, 15, 6]
BROKEN = [
    "this is not a log line",
    '203.0.113.5 - - [01/Oct/2026:10:00:00 +0200] "GET /broken',
    '203.0.113.5 - - [32/Oct/2026:10:00:00 +0200] "GET / HTTP/1.1" 200 12 "-" "curl"',
    '203.0.113.5 - - [01/Oct/2026:10:00:00 +0200] "GET / HTTP/1.1" 999 12 "-" "curl"',
    "",
    '\x00\x00binary garbage\x00',
]

lines = []
for _ in range(3000):
    day = random.randrange(7)
    hour = random.choices(range(24), weights=HOUR_WEIGHTS)[0]
    t = START + timedelta(days=day, hours=hour, minutes=random.randrange(60), seconds=random.randrange(60))
    ip = random.choice(HOT) if random.random() < 0.25 else random.choice(IPS)
    status = random.choice(STATUSES)
    size = "-" if status == 304 else str(random.randint(80, 50000))
    line = (f'{ip} - - [{t.strftime("%d/%b/%Y:%H:%M:%S %z")}] '
            f'"{random.choice(["GET"] * 8 + ["POST", "PUT"])} {random.choice(PATHS)} HTTP/1.1" '
            f'{status} {size} "-" "{random.choice(AGENTS)}"')
    lines.append((t, line))
lines.sort()
text = [line for _, line in lines]
for i, bad in enumerate(BROKEN):
    text.insert(400 * (i + 1), bad)
OUT.write_text("\n".join(text) + "\n", encoding="utf-8")
print(f"{OUT}: {len(text)} рядків, із них пошкоджених {len(BROKEN) - 1} (+1 порожній)")
