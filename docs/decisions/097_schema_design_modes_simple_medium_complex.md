# 097 - Schema Design Modes (`simple` / `medium` / `complex`) for `schema_project_v2`

## Context
- `schema_project_v2` accumulated advanced DG authoring controls across project, table, column, and relationship panels.
- The route needed progressive disclosure without introducing additional schema-authoring routes or changing schema/runtime semantics.
- Product choice was a single route with live mode switching and default `simple` behavior.

## Decision
- Added a shared mode policy module: `src/gui_v2/schema_design_modes.py`.
  - Defines `SchemaDesignMode` (`simple|medium|complex`), default `simple`, normalization helpers, downgrade detection, and generator allowlists.
- Implemented mode state and UI application in `src/gui_schema_editor_base.py`.
  - Added `schema_design_mode_var` and mode apply helpers.
  - Added grouped panel visibility toggles (`grid_remove()/grid()`) for project/table/column/relationship advanced sections.
  - Kept all hidden values intact (no clearing when mode downgrades).
  - Added non-blocking downgrade feedback when advanced values are hidden.
- Added header segmented selector in `src/gui_v2_schema_project.py`.
  - `Simple | Medium | Complex` switches mode immediately.
  - Mode changes persist in route workspace state.
- Integrated mode policy into generator UX.
  - Generator combo values are filtered by `dtype + mode allowlist`.
  - Existing out-of-mode selected generator remains visible/selected and is preserved.
  - Structured generator form behavior:
    - `simple`: hidden,
    - `medium`: visible (advanced subsection hidden),
    - `complex`: full structured form including advanced subsection.
- Extended workspace payload persistence in `src/gui_schema_editor_base.py`.
  - Added optional route state key: `schema_design_mode`.
  - Backward-compatible restore defaults missing values to `simple`.
- Added regression coverage:
  - `tests/test_gui_schema_design_modes.py` (default mode, visibility matrix, downgrade preservation, workspace restore),
  - `tests/test_gui_workspace_state_persistence.py` (mode persistence assertion).

## Consequences
- `schema_project_v2` now scales from basic to advanced authoring in one route without adding route complexity.
- UI complexity is reduced for default users while advanced DG controls remain available on demand.
- Schema JSON contracts, runtime generation behavior, and validator contracts remain unchanged.
- Downgrading mode is safe: hidden advanced settings and out-of-mode generator selections are preserved through edit/save/load flows.
