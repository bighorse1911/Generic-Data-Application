# Test Layout Guide

Tests are grouped by subsystem for easier discovery.

## Folders

- `tests/schema/`: schema model, schema IO, schema-level contracts.
- `tests/generation/`: row generation logic, generators, DG features.
- `tests/runtime/`: performance and multiprocessing execution runtimes.
- `tests/gui/`: GUI behavior, route parity, widget/tooling tests.
- `tests/integration/`: cross-domain end-to-end invariants and flows.
- `tests/fixtures/`: shared fixture assets used by multiple suites.

## Discovery Contract

- Keep all test filenames as `test_*.py`.
- `unittest` discovery starts at `tests/` and recursively finds tests.
- Subfolders are layout only; behavior contracts remain unchanged.

## Guardrails

- `tests/test_import_contracts.py` verifies legacy import compatibility.
- `tests/test_module_size_budget.py` enforces incremental module-size budgets.

## GUI Execution Guidance

- Preferred for GUI: `python run_gui_tests_isolated.py` (isolated per-module subprocess runs).
- Optional timeout override: `python run_gui_tests_isolated.py --timeout 90`.
- Keep standard `unittest discover` for non-GUI suites unchanged.
