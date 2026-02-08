import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import run_tests_with_logs as runner


class TestRunTestsWithLogs(unittest.TestCase):
    def test_failure_log_path_is_timestamped(self):
        log_dir = Path("tests") / "testlogs"
        path = runner._failure_log_path(log_dir, datetime(2026, 2, 8, 13, 45, 7))
        self.assertEqual(
            path.name,
            "test_failures_20260208_134507.txt",
            "Failure log filename format mismatch. "
            "Fix: use test_failures_YYYYMMDD_HHMMSS.txt naming.",
        )

    def test_write_failure_report_creates_text_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "testlogs"
            content = "example failure report"
            path = runner._write_failure_report(
                log_dir,
                content,
                datetime(2026, 2, 8, 13, 45, 7),
            )
            self.assertTrue(
                path.exists(),
                "Failure report file was not created. "
                "Fix: ensure _write_failure_report() creates parent directory and writes the file.",
            )
            self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_build_failure_report_includes_summary_and_fix_hint(self):
        result = unittest.TestResult()
        result.testsRun = 3
        result.failures = [("test_case", "traceback")]
        result.errors = []

        report = runner._build_failure_report(result, "sample unittest output")
        self.assertIn("Summary: ran=3, failures=1, errors=0", report)
        self.assertIn("Fix hint:", report)
        self.assertIn("sample unittest output", report)


if __name__ == "__main__":
    unittest.main()
