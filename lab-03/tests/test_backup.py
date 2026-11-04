"""Тести backup.sh: сценарії з розділу «Як перевіряється» завдання 1."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
SCRIPT = LAB / "backup.sh"


def find_bash() -> str | None:
    # На Windows `bash` у PATH може виявитися WSL-обгорткою, яка не розуміє шляхів C:\ —
    # тому спершу Git Bash.
    for candidate in (os.environ.get("BASH_FOR_TESTS"), r"C:\Program Files\Git\bin\bash.exe"):
        if candidate and Path(candidate).is_file():
            return candidate
    return shutil.which("bash")


BASH = find_bash()


@unittest.skipIf(BASH is None, "bash не знайдено")
class BackupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="backup test "))  # пробіл у шляху — навмисно
        self.src = self.tmp / "my project"
        (self.src / "src").mkdir(parents=True)
        (self.src / "src" / "a.txt").write_text("hello")
        self.dest = self.tmp / "dest dir"
        self.dest.mkdir()
        # чужі файли, які ротація не має чіпати
        self.foreign = ["notes.txt", "other-2026-01-01-000000.tar.gz", "my project-old.tar.gz"]
        for name in self.foreign:
            (self.dest / name).write_text("foreign")
        self.env = {**os.environ, "BACKUP_LOG": str(self.tmp / "backup.log")}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_backup(self, *args):
        return subprocess.run([BASH, str(SCRIPT), *args], check=False, capture_output=True, text=True,
                              encoding="utf-8", env=self.env)

    def archives(self):
        return sorted(p.name for p in self.dest.glob("my project-2*.tar.gz"))

    def test_six_runs_keep_three(self):
        for _ in range(6):
            r = self.run_backup("--source", str(self.src), "--dest", str(self.dest), "--keep", "3")
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.archives()), 3)
        for name in self.foreign:
            self.assertTrue((self.dest / name).exists(), f"ротація видалила чужий файл {name}")

    def test_missing_source(self):
        r = self.run_backup("--source", str(self.tmp / "nope"), "--dest", str(self.dest))
        self.assertEqual(r.returncode, 2)
        self.assertIn("джерело не існує", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_missing_required_param(self):
        r = self.run_backup("--dest", str(self.dest))
        self.assertEqual(r.returncode, 1)
        self.assertIn("--source", r.stderr)

    def test_dry_run_deletes_nothing(self):
        for _ in range(5):
            self.run_backup("--source", str(self.src), "--dest", str(self.dest))
        before = self.archives()
        r = self.run_backup("--source", str(self.src), "--dest", str(self.dest), "--keep", "3", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.count("[dry-run] видалити"), 3)
        self.assertEqual(self.archives(), before)

    def test_dest_created(self):
        new_dest = self.tmp / "new dest"
        r = self.run_backup("--source", str(self.src), "--dest", str(new_dest))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(list(new_dest.glob("*.tar.gz"))), 1)

    def test_log_written(self):
        self.run_backup("--source", str(self.src), "--dest", str(self.dest))
        log = (self.tmp / "backup.log").read_text(encoding="utf-8")
        self.assertRegex(log, r"action=backup result=ok .*size_bytes=\d+ deleted=0")


if __name__ == "__main__":
    unittest.main()
