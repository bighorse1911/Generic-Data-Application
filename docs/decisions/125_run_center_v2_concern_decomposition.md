# 125 - Run Center v2 Concern Decomposition

## Context

- `src/gui/v2/routes/run_center_impl.py` remained a large mixed-concern module (~600 LOC) combining navigation/shortcuts, schema/config IO, and run lifecycle execution handling.
- Run Center v2 is part of the v2 route family and must preserve no-behavior-change compatibility with:
  - route keys and screen exports,
  - legacy shim patch points through `src.gui_v2_redesign`,
  - deterministic run lifecycle and error-message contracts.
- This slice required keeping hook indirection through `src/gui/v2/routes/run_hooks.py` so legacy patch targets continue to affect runtime behavior.

## Decision

- Decompose Run Center concerns into dedicated modules:
  - `src/gui/v2/routes/run_center_nav.py`
  - `src/gui/v2/routes/run_center_io.py`
  - `src/gui/v2/routes/run_center_runs.py`
- Convert `src/gui/v2/routes/run_center_impl.py` into a thin compatibility facade that:
  - keeps `RunCenterV2Screen` in place,
  - preserves constructor wiring and method names,
  - delegates concern methods to extracted modules.
- Preserve hook indirection by keeping runtime actions routed through the `run_hooks` module object in extracted logic.
- Add contract coverage:
  - `tests/gui/test_run_center_v2_method_contracts.py` for extracted-method exports and wrapper delegation,
  - `tests/test_import_contracts.py` module-import guardrails for new route concern modules.

## Consequences

- Run Center behavior remains unchanged while ownership is clearer by concern.
- Legacy patch points (`src.gui_v2_redesign.*`) continue to affect Run Center runtime flows through unchanged hook-bridge semantics.
- The run-center facade is now easier to navigate and future hotspot decomposition can continue from smaller concern-owned modules.
