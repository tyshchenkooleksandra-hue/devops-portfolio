#!/usr/bin/env python3
"""Монітор доступності API: перевіряє endpoint'и зі списку й розрізняє типи збою.

Типи збою відповідають етапу, на якому зупинився запит:
DNS → TCP-з'єднання → TLS → HTTP-відповідь → час відповіді.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

EXIT_OK = 0  # усі цілі здорові
EXIT_UNHEALTHY = 1  # хоча б одна ціль має проблему
EXIT_CONFIG = 2  # неправильні параметри або конфігурація

SCRIPT_DIR = Path(__file__).resolve().parent
WEBHOOK_ENV = "DISCORD_WEBHOOK_URL"
USER_AGENT = "api_monitor/1.0 (devops-portfolio lab-03)"

# Тип збою → людський опис. Ключ іде в структурований файл, опис — у журнал і сповіщення.
FAILURES = {
    "dns": "DNS: ім'я не резолвиться",
    "connection_refused": "З'єднання відхилено: на порту ніхто не слухає",
    "timeout": "Тайм-аут: немає відповіді у відведений час",
    "tls_certificate": "Помилка сертифіката: TLS-з'єднання відхилено",
    "unexpected_status": "Несподіваний код відповіді",
    "slow_response": "Повільна відповідь: перевищено поріг",
    "network": "Інша мережева помилка",
}
# Повторюємо лише мережеві збої: вони бувають тимчасовими. Сертифікат чи неправильний
# код від повтору не зміняться — повтор лише затримав би сповіщення.
RETRYABLE = {"dns", "connection_refused", "timeout", "network"}
RETRY_DELAY_S = 1.0


class ConfigError(Exception):
    """Помилка конфігурації — показується користувачу без трасування."""


class CheckFailure(Exception):
    def __init__(self, kind: str, detail: str, http_status: int | None = None):
        super().__init__(detail)
        self.kind = kind
        self.detail = detail
        self.http_status = http_status  # для unexpected_status / slow_response код відомий


@dataclass
class Target:
    name: str
    url: str
    expected_status: int
    timeout_s: float
    slow_ms: int


@dataclass
class Result:
    time: str
    target: str
    url: str
    status: str  # "ok" | "fail"
    http_status: int | None
    response_ms: int | None
    failure_type: str | None
    detail: str | None
    attempts: int


# ---------------------------------------------------------------- конфігурація
def load_config(path: Path) -> list[Target]:
    if not path.is_file():
        raise ConfigError(f"файл конфігурації не знайдено: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path}: некоректний JSON у рядку {e.lineno}, стовпці {e.colno}: {e.msg}") from None

    defaults = data.get("defaults", {})
    targets_raw = data.get("targets")
    if not isinstance(targets_raw, list) or not targets_raw:
        raise ConfigError(f"{path}: потрібен непорожній список 'targets'")

    targets = []
    for i, raw in enumerate(targets_raw, 1):
        merged = {**defaults, **raw}
        where = f"{path}: ціль №{i}"
        url = merged.get("url")
        if not isinstance(url, str) or urlsplit(url).scheme not in ("http", "https") or not urlsplit(url).hostname:
            raise ConfigError(f"{where}: 'url' має бути адресою http:// або https://, отримано {url!r}")
        try:
            target = Target(
                name=str(merged.get("name") or urlsplit(url).hostname),
                url=url,
                expected_status=int(merged.get("expected_status", 200)),
                timeout_s=float(merged.get("timeout_s", 5)),
                slow_ms=int(merged.get("slow_ms", 2000)),
            )
        except (TypeError, ValueError) as e:
            raise ConfigError(f"{where}: числові поля мають бути числами ({e})") from None
        if target.timeout_s <= 0 or target.slow_ms <= 0:
            raise ConfigError(f"{where}: timeout_s і slow_ms мають бути додатними")
        targets.append(target)
    return targets


# ---------------------------------------------------------------- перевірка
def check_once(target: Target) -> tuple[int, int]:
    """Один запит. Повертає (HTTP-код, мс) або кидає CheckFailure з типом збою."""
    parts = urlsplit(target.url)
    host = parts.hostname
    https = parts.scheme == "https"
    port = parts.port or (443 if https else 80)
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")

    start = time.monotonic()
    # Етап 1 — DNS. Окремо, щоб не плутати «ім'я не існує» з «сервер не відповідає».
    try:
        socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise CheckFailure("dns", f"{host}: {e.strerror}") from None

    if https:
        conn = http.client.HTTPSConnection(host, port, timeout=target.timeout_s, context=ssl.create_default_context())
    else:
        conn = http.client.HTTPConnection(host, port, timeout=target.timeout_s)
    try:
        # Етапи 2–4 — TCP, TLS, HTTP.
        conn.request("GET", path, headers={"User-Agent": USER_AGENT})
        resp = conn.getresponse()
        resp.read()
        status = resp.status
    except ConnectionRefusedError:
        raise CheckFailure("connection_refused", f"{host}:{port} відповів RST — порт закритий") from None
    except TimeoutError:
        raise CheckFailure("timeout", f"{host}:{port} не відповів за {target.timeout_s:g} с") from None
    except ssl.SSLCertVerificationError as e:
        raise CheckFailure("tls_certificate", f"{host}: {e.verify_message}") from None
    except (ssl.SSLError, OSError, http.client.HTTPException) as e:
        raise CheckFailure("network", f"{host}:{port}: {type(e).__name__}: {e}") from None
    finally:
        conn.close()
    elapsed_ms = round((time.monotonic() - start) * 1000)

    # Етап 5 — зміст відповіді.
    if status != target.expected_status:
        raise CheckFailure("unexpected_status", f"очікувався {target.expected_status}, отримано {status}", status)
    if elapsed_ms > target.slow_ms:
        raise CheckFailure("slow_response", f"{elapsed_ms} мс > порогу {target.slow_ms} мс", status)
    return status, elapsed_ms


def check(target: Target) -> Result:
    attempts = 0
    failure: CheckFailure | None = None
    status = elapsed = None
    for attempt in (1, 2):
        attempts = attempt
        t0 = time.monotonic()
        try:
            status, elapsed = check_once(target)
            failure = None
            break
        except CheckFailure as f:
            failure = f
            elapsed = round((time.monotonic() - t0) * 1000)
            if f.kind not in RETRYABLE or attempt == 2:
                break
            time.sleep(RETRY_DELAY_S)

    if failure:
        status = failure.http_status
    return Result(
        time=datetime.now().astimezone().isoformat(timespec="seconds"),
        target=target.name,
        url=target.url,
        status="fail" if failure else "ok",
        http_status=status,
        response_ms=elapsed,
        failure_type=failure.kind if failure else None,
        detail=failure.detail if failure else None,
        attempts=attempts,
    )


# ---------------------------------------------------------------- вивід
def log_line(r: Result) -> str:
    base = f"{r.time} target={r.target} status={r.status.upper()}"
    if r.status == "ok":
        return f"{base} http={r.http_status} response_ms={r.response_ms}"
    return f"{base} type={r.failure_type} attempts={r.attempts} — {FAILURES[r.failure_type]}: {r.detail}"


def notify(results: list[Result], log) -> None:
    # strip(): пробіл чи перенос рядка, скопійований разом з URL, — часта причина «тихого» збою
    webhook = os.environ.get(WEBHOOK_ENV, "").strip()
    failed = [r for r in results if r.status == "fail"]
    if not failed:
        return
    if not webhook:
        log(f"сповіщення пропущено: змінну {WEBHOOK_ENV} не задано")
        return
    for r in failed:
        text = (
            f"🔴 **{r.target}** — {FAILURES[r.failure_type]}\n"
            f"тип: `{r.failure_type}` · спроб: {r.attempts}\n"
            f"{r.url}\n{r.detail}"
        )
        body = json.dumps({"content": text}).encode()
        req = urllib.request.Request(
            webhook, data=body, method="POST",
            headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        )
        try:
            with urllib.request.urlopen(req, timeout=10):
                pass
            log(f"сповіщення надіслано: {r.target} ({r.failure_type})")
        except (urllib.error.URLError, TimeoutError) as e:
            # Збій месенджера не має ховати результат перевірки — лише попередження.
            log(f"попередження: сповіщення для {r.target} не надіслано: {e}")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="api_monitor.py",
        description="Перевіряє доступність endpoint'ів зі списку й розрізняє типи збою: "
        "DNS, з'єднання відхилено, тайм-аут, сертифікат, несподіваний код, повільна відповідь.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""\
коди виходу:
  0  усі цілі здорові
  1  є проблемні цілі
  2  неправильні параметри або конфігурація

сповіщення: Discord-вебхук зі змінної середовища {WEBHOOK_ENV} (не з коду й не з конфігурації)

приклад:
  export {WEBHOOK_ENV}='https://discord.com/api/webhooks/…'
  python api_monitor.py --config config/targets.json
  python api_monitor.py --config config/targets.json --no-notify""",
    )
    p.add_argument("--config", type=Path, default=SCRIPT_DIR / "config" / "targets.json",
                   help="JSON зі списком цілей (типово: %(default)s)")
    p.add_argument("--results", type=Path, default=SCRIPT_DIR / "logs" / "api_monitor.jsonl",
                   help="куди дописувати результати, JSON Lines (типово: %(default)s)")
    p.add_argument("--log", type=Path, default=SCRIPT_DIR / "logs" / "api_monitor.log",
                   help="журнал запусків (типово: %(default)s)")
    p.add_argument("--no-notify", action="store_true", help="не надсилати сповіщення")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        targets = load_config(args.config)
    except ConfigError as e:
        print(f"api_monitor.py: помилка конфігурації: {e}", file=sys.stderr)
        return EXIT_CONFIG

    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.results.parent.mkdir(parents=True, exist_ok=True)

    with args.log.open("a", encoding="utf-8") as log_file:
        def log(msg: str) -> None:
            print(msg)
            log_file.write(msg + "\n")

        started = datetime.now().astimezone().isoformat(timespec="seconds")
        log(f"{started} action=run targets={len(targets)} config={args.config}")
        results = [check(t) for t in targets]
        with args.results.open("a", encoding="utf-8") as out:
            for r in results:
                log(log_line(r))
                out.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")

        failed = sum(r.status == "fail" for r in results)
        log(f"{datetime.now().astimezone().isoformat(timespec='seconds')} action=summary "
            f"result={'ok' if not failed else 'problems'} healthy={len(results) - failed} failed={failed}")
        if not args.no_notify:
            notify(results, log)

    return EXIT_UNHEALTHY if failed else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
