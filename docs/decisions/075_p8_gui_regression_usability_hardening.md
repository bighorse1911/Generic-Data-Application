# 075 - P8 GUI Regression/Usability Hardening

Date: 2026-02-16

## Context
- Priority P8 in `NEXT_DECISIONS.md` required a v2-first hardening slice focused on regression/usability confidence, not feature expansion.
- Existing tests already covered broad route contracts and shared lifecycle units, but scenario coverage for v2 transitions, guarded navigation outcomes, bridge parity, and run-center cancel/fallback usability states needed to be explicit.
- Constraints required deterministic tests, additive behavior only, no runtime/data semantic changes, and no new dependencies.

## Decision
- Added small additive observability/usability hooks:
  - `src/gui_home.py`: read-only `App.current_screen_name`.
  - `src/gui_v2_redesign.py`:
    - `V2ShellFrame.active_nav_key` read-only state for nav selection assertions.
    - `SchemaStudioV2Screen._navigate_with_guard(...)` now maps blocked reasons to explicit status outcomes (`user_cancelled`, `guard_error`, fallback blocked message).
- Added dedicated scenario suite:
  - `tests/test_gui_p8_regression_usability.py`
  - Covers:
    - v2 route transition stability and active-route tracking,
    - schema-studio section selection/nav/status behavior,
    - dirty guard block/allow/error outcomes against primary schema route,
    - `*_v2_bridge` launch-through parity,
    - run-center shortcut lifecycle toggling, cancel gating, fallback start path, output-path cancellation no-op, partition-failure event handling, and cancelled/failed terminal-state history behavior.
- Extended targeted existing tests:
  - `tests/test_gui_v2_feature_c.py`: guard error contract and blocked guarded-navigation no-op.
  - `tests/test_gui_run_workflow_convergence.py`: run-center shortcut lifecycle across route switches.
  - `tests/test_schema_route_consolidation.py`: schema-studio integration check for primary dirty-screen guard block/allow.
- Updated governance/docs:
  - `GUI_WIREFRAME_SCHEMA.md`
  - `PROJECT_CANON.md`
  - `NEXT_DECISIONS.md`

## Consequences
- v2 regression confidence is now scenario-oriented, not just widget-presence smoke tests.
- Guarded-navigation failures are clearer to users and easier to assert in tests.
- Run-center cancel/fallback UX behavior is explicitly covered without changing runtime semantics.
- Rollback bridge routes now have explicit parity checks validating launch-through behavior.

## Rollback Notes
- New runtime-facing behavior is limited to additive status text mapping and read-only observability properties.
- If needed, rollback can remove new status mapping/properties while retaining tests that do not depend on those hooks.
- P8 tests are isolated and can be deselected independently if a future suite split is required.
