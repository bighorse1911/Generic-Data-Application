# 086 - P17 Notification Center and Reduced Modal Friction

## Context
- Priority P17 in `NEXT_DECISIONS.md` targeted workflow interruption caused by informational/success modal dialogs.
- `schema_project_v2` still inherited blocking `showinfo` completion dialogs from shared schema-core behavior.
- Interactive routes lacked a shared notification history surface for reviewing recent non-critical events.

## Decision
- Extend `src/gui_kit/feedback.py` into a full notification center model:
  - add `NotificationCenter` + `NotificationEntry`,
  - keep `ToastCenter` as backward-compatible alias,
  - add bounded in-memory history and history dialog presentation.
- Update shared schema core (`src/gui_schema_core.py`) to replace non-critical info/success modals with notifications:
  - generation completion,
  - CSV export completion,
  - SQLite completion,
  - validation heatmap informational feedback.
- Route non-critical schema warnings (for example "Generate data first") to non-modal status + notification instead of warning modal dialogs.
- Add discoverable notification-history actions on interactive route headers (`schema_project_v2`, `run_center_v2`, `performance_workbench_v2`, `execution_orchestrator_v2`, and classic schema/performance/orchestrator bases).
- Add notification emission on high-frequency completion flows (estimate/plan/benchmark/run/save/load completions in run routes).

## Consequences
- Routine informational/success feedback is now non-blocking and reviewable via history.
- Blocking dialogs remain in place for decisions and actionable error interruptions.
- `schema_project_v2` no longer surfaces inherited blocking info dialogs for generate/export completion.
- Added regression coverage:
  - `tests/test_gui_kit_notifications.py`,
  - `tests/test_gui_notifications_integration.py`,
  - updated modal/static contract checks in `tests/test_gui_error_surface_static_gate.py` and `tests/test_gui_error_contract_matrix.py`.
