"""Тести розбору одного рядка журналу, включно з некоректними рядками."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import log_analyzer as la

GOOD = '203.0.113.7 - frank [10/Oct/2026:20:55:36 +0200] "GET /api/v1/items HTTP/1.1" 200 2326 "-" "curl/8.19.0"'


class ParseLineTest(unittest.TestCase):
    def test_valid_combined_line(self):
        e = la.parse_line(GOOD)
        self.assertIsNotNone(e)
        self.assertEqual((e.ip, e.method, e.path, e.status, e.size), ("203.0.113.7", "GET", "/api/v1/items", 200, 2326))
        self.assertEqual(e.time.hour, 20)

    def test_common_format_without_referer_agent(self):
        e = la.parse_line('198.51.100.3 - - [01/Oct/2026:09:00:00 +0200] "POST /login HTTP/1.1" 401 -')
        self.assertEqual((e.status, e.size), (401, 0))

    def test_malformed_lines_return_none(self):
        for bad in [
            "",
            "this is not a log line",
            '203.0.113.5 - - [01/Oct/2026:10:00:00 +0200] "GET /broken',        # обірваний рядок
            '203.0.113.5 - - [32/Oct/2026:10:00:00 +0200] "GET / HTTP/1.1" 200 12 "-" "c"',  # неіснуюча дата
            '203.0.113.5 - - [01/Oct/2026:10:00:00 +0200] "GET / HTTP/1.1" 999 12 "-" "c"',  # код поза 100–599
            "\x00\x00binary\x00",
        ]:
            with self.subTest(line=bad):
                self.assertIsNone(la.parse_line(bad))

    def test_analyze_counts_malformed_separately(self):
        r = la.analyze([GOOD, "garbage", GOOD.replace(" 200 ", " 503 "), ""], top=5)
        self.assertEqual((r["lines_total"], r["lines_parsed"], r["lines_malformed"]), (3, 2, 1))
        self.assertEqual(r["status_classes"]["2xx"], 1)
        self.assertEqual(r["status_classes"]["5xx"], 1)
        self.assertEqual(r["peak_hours"], ["20:00"])


if __name__ == "__main__":
    unittest.main()
