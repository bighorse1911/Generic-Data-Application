from __future__ import annotations

import argparse
import sys

from src.experimental.pyqt_schema_project.launcher import check_pyqt6_available


def _error(location: str, issue: str, hint: str) -> str:
    return f"{location}: {issue}. Fix: {hint}."


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Optional PyQt schema-project experiment")
    parser.add_argument("--schema", default="", help="Optional schema JSON path to open on startup.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    available, message = check_pyqt6_available()
    if not available:
        sys.stderr.write((message or "PyQt6 is not available") + "\n")
        return 2

    try:
        from PyQt6.QtWidgets import QApplication
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(
            _error(
                "PyQt experiment bootstrap",
                f"failed to import QApplication ({exc})",
                "install a working PyQt6 runtime",
            )
            + "\n"
        )
        return 2

    try:
        from src.experimental.pyqt_schema_project.window import ExperimentalSchemaProjectWindow
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(
            _error(
                "PyQt experiment bootstrap",
                f"failed to import window module ({exc})",
                "verify the experimental package files are present and valid",
            )
            + "\n"
        )
        return 2

    app = QApplication(sys.argv)
    window = ExperimentalSchemaProjectWindow(initial_schema_path=args.schema.strip() or None)
    window.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
