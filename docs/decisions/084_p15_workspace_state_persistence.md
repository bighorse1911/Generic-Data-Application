# 084 - P15 Workspace State Persistence

## Context
- Priority P15 in `NEXT_DECISIONS.md` required restoring user workflow context across app restarts.
- `schema_project_v2` previously reset panel/tab/preview preferences on each new app session.
- Loss of route-local UI state increased repeated setup work during iterative schema authoring.

## Decision
- Add a versioned workspace preferences store in `src/gui_kit/preferences.py`:
  - route-keyed state payloads,
  - JSON persistence with schema version marker,
  - default path resolution with `GDA_WORKSPACE_STATE_PATH` override for tests.
- Initialize one app-level store in `App` (`src/gui_home.py`) and expose it to route screens.
- Integrate state persistence in `SchemaEditorBaseScreen` for `schema_project_v2`:
  - restore on screen build,
  - persist on route hide and screen destroy,
  - persist on active-tab changes, preview page-size changes, and preview column-chooser apply.
- Persisted state scope:
  - panel collapse state (`project`, `tables`, `columns`, `relationships`, `generate`),
  - active main tab,
  - preview page size,
  - preview visible-column order/preferences per table.

## Consequences
- Users retain route-level workspace continuity after restart without manual reconfiguration.
- Persistence failures remain non-blocking (best-effort) and do not interrupt authoring flows.
- Added regression coverage:
  - `tests/test_gui_kit_preferences.py` for store roundtrip,
  - `tests/test_gui_workspace_state_persistence.py` for schema-route restore behavior across app instances.
