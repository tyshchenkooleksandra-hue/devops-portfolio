"""Тести api_monitor.py без зовнішньої мережі (крім DNS для зарезервованого .invalid)."""

import json
import socket
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import api_monitor as m


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/slow":
            time.sleep(0.6)
        code = 503 if self.path == "/broken" else 200
        self.send_response(code)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class MonitorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        m.RETRY_DELAY_S = 0  # не чекати в тестах

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def target(self, url, **kw):
        return m.Target(name="t", url=url, expected_status=kw.get("expected", 200),
                        timeout_s=kw.get("timeout", 2), slow_ms=kw.get("slow_ms", 5000))

    def test_ok(self):
        r = m.check(self.target(self.base + "/"))
        self.assertEqual((r.status, r.http_status, r.failure_type), ("ok", 200, None))

    def test_unexpected_status_not_retried(self):
        r = m.check(self.target(self.base + "/broken"))
        self.assertEqual((r.failure_type, r.http_status, r.attempts), ("unexpected_status", 503, 1))

    def test_slow_response(self):
        r = m.check(self.target(self.base + "/slow", slow_ms=200))
        # код відповіді правильний — він має зберегтися в результаті
        self.assertEqual((r.failure_type, r.http_status), ("slow_response", 200))

    def test_connection_refused_retried_once(self):
        # Windows після RST ще ~2 с повторює SYN, тому тайм-аут має бути більшим за цю затримку,
        # інакше «відхилено» перетвориться на «тайм-аут».
        r = m.check(self.target(f"http://127.0.0.1:{free_port()}/", timeout=5))
        self.assertEqual((r.failure_type, r.attempts), ("connection_refused", 2))

    def test_dns(self):
        r = m.check(self.target("https://no-such-host.invalid/"))
        self.assertEqual(r.failure_type, "dns")

    def test_config_errors_are_messages(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad.json"
            bad.write_text('{"targets": [', encoding="utf-8")
            with self.assertRaisesRegex(m.ConfigError, "некоректний JSON"):
                m.load_config(bad)
            bad.write_text(json.dumps({"targets": [{"url": "ftp://x"}]}), encoding="utf-8")
            with self.assertRaisesRegex(m.ConfigError, "url"):
                m.load_config(bad)
            with self.assertRaisesRegex(m.ConfigError, "не знайдено"):
                m.load_config(Path(d) / "missing.json")

    def test_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / "c.json"
            common = ["--no-notify", "--log", str(Path(d) / "l"), "--results", str(Path(d) / "r")]
            cfg.write_text(json.dumps({"targets": [{"url": self.base + "/"}]}), encoding="utf-8")
            self.assertEqual(m.main(["--config", str(cfg), *common]), m.EXIT_OK)
            cfg.write_text(json.dumps({"targets": [{"url": self.base + "/broken"}]}), encoding="utf-8")
            self.assertEqual(m.main(["--config", str(cfg), *common]), m.EXIT_UNHEALTHY)
            self.assertEqual(m.main(["--config", str(Path(d) / "none.json"), *common]), m.EXIT_CONFIG)
            # структурований результат: кожен рядок — JSON з обов'язковими полями
            rows = [json.loads(x) for x in (Path(d) / "r").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(set(rows[-1]), {"time", "target", "url", "status", "http_status",
                                             "response_ms", "failure_type", "detail", "attempts"})


if __name__ == "__main__":
    unittest.main()
