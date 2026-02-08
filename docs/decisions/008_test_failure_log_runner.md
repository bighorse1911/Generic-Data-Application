# Context
- Prompt requested a single call/script to run all unit tests and write failures to a timestamped text file.
- Prompt also requested adding the `tests/testlogs` folder.

# Decision
- Added `run_tests_with_logs.py` at repo root.
- Script behavior:
  - Discovers/runs all unit tests with `unittest` (`tests`, `test_*.py`).
  - Streams full test output to console.
  - If failures/errors exist, writes a timestamped failure report to `tests/testlogs/test_failures_YYYYMMDD_HHMMSS.txt`.
  - If all tests pass, no failure log file is created.
- Added `tests/testlogs/.gitkeep` to ensure the folder exists in version control.
- Added `tests/test_run_tests_with_logs.py` to verify timestamped naming and file creation behavior.

# Consequences
- Running all tests is now one command: `python run_tests_with_logs.py`.
- Failure details are preserved in timestamped files for debugging and history.
- No changes to generation, FK logic, GUI flows, or schema JSON IO behavior.
