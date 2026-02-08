from __future__ import annotations

import io
import sys
import unittest
from datetime import datetime
from pathlib import Path


def _timestamp(now: datetime | None = None) -> str:
    ts = now or datetime.now()
    return ts.strftime("%Y%m%d_%H%M%S")


def _failure_log_path(log_dir: Path, now: datetime | None = None) -> Path:
    return log_dir / f"test_failures_{_timestamp(now)}.txt"


def _build_failure_report(result: unittest.result.TestResult, test_output: str) -> str:
    lines: list[str] = []
    lines.append(f"Timestamp: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(
        "Summary: "
        f"ran={result.testsRun}, failures={len(result.failures)}, errors={len(result.errors)}"
    )
    lines.append("Fix hint: inspect stack traces below, fix failing tests, then rerun this script.")
    lines.append("")
    lines.append(test_output.rstrip())
    lines.append("")
    return "\n".join(lines)


def _write_failure_report(log_dir: Path, content: str, now: datetime | None = None) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = _failure_log_path(log_dir, now)
    path.write_text(content, encoding="utf-8")
    return path


def main() -> int:
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="tests", pattern="test_*.py")

    output = io.StringIO()
    runner = unittest.TextTestRunner(stream=output, verbosity=2)
    result = runner.run(suite)

    test_output = output.getvalue()
    sys.stdout.write(test_output)

    if result.wasSuccessful():
        print("All tests passed. No failure log written.")
        return 0

    log_dir = Path("tests") / "testlogs"
    report = _build_failure_report(result, test_output)
    log_path = _write_failure_report(log_dir, report)
    print(f"Test failures detected. Log written to: {log_path}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
