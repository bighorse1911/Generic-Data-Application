from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModuleResult:
    module: str
    status: str
    elapsed_s: float
    detail: str


def _discover_gui_test_modules(gui_tests_dir: Path) -> list[str]:
    modules: list[str] = []
    for path in sorted(gui_tests_dir.glob("test_*.py")):
        modules.append(f"tests.gui.{path.stem}")
    return modules


def _run_module(module: str, timeout_s: int) -> ModuleResult:
    start = time.perf_counter()
    cmd = [sys.executable, "-m", "unittest", module]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        elapsed = time.perf_counter() - start
        return ModuleResult(module=module, status="timeout", elapsed_s=elapsed, detail=f"timeout>{timeout_s}s")

    elapsed = time.perf_counter() - start
    if completed.returncode == 0:
        return ModuleResult(module=module, status="ok", elapsed_s=elapsed, detail="OK")

    output = (completed.stdout + "\n" + completed.stderr).strip().splitlines()
    detail = output[-1].strip() if output else "non-zero exit"
    return ModuleResult(module=module, status="fail", elapsed_s=elapsed, detail=detail)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run tests/gui modules in isolated subprocesses to avoid Tk lifecycle "
            "cross-test interference while preserving deterministic per-module results."
        )
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Per-module timeout in seconds (default: 60).",
    )
    args = parser.parse_args()

    gui_tests_dir = Path("tests/gui")
    if not gui_tests_dir.exists():
        print("No tests/gui directory found.")
        return 1

    modules = _discover_gui_test_modules(gui_tests_dir)
    if not modules:
        print("No GUI test modules found.")
        return 1

    print(f"Running {len(modules)} GUI modules with per-module timeout={args.timeout}s")
    print("-" * 80)

    results: list[ModuleResult] = []
    for module in modules:
        result = _run_module(module, timeout_s=args.timeout)
        results.append(result)
        print(f"[{result.status.upper():7}] {module} ({result.elapsed_s:.2f}s) - {result.detail}")

    failures = [r for r in results if r.status != "ok"]
    print("-" * 80)
    print(
        "Summary: "
        f"total={len(results)}, passed={len(results) - len(failures)}, "
        f"failed_or_timed_out={len(failures)}"
    )

    if failures:
        print("Failures/timeouts:")
        for failure in failures:
            print(f"- {failure.module}: {failure.status} ({failure.detail})")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
