# 094 - DG06 Missingness + Data-Quality Profiles

## Context
- `NEXT_DECISIONS.md` prioritized DG06 to add realistic null behavior and controllable data-quality defects.
- Existing behavior only supported column-local `null_rate` and numeric outlier scaling; no project-level missingness/quality profile model existed.
- DG06 required additive deterministic behavior, canonical actionable validation/runtime errors, JSON roundtrip support, and GUI authoring exposure.

## Decision
- Extended project contract in `src/schema_project_model.py`:
  - added optional `SchemaProject.data_quality_profiles`.
  - validated profile shape and semantics for:
    - `kind="missingness"` with `mcar`/`mar`/`mnar`,
    - `kind="quality_issue"` with `format_error`/`stale_value`/`drift`,
    - profile ids, table/column existence, `where` predicates, and numeric bounds.
  - enforced canonical actionable validation errors (`<Location>: <issue>. Fix: <hint>.`).
- Implemented deterministic DG06 runtime in `src/generator_project.py`:
  - added compiler for profile configs with strict runtime guardrails.
  - added table-level profile application pass after DG03 timeline enforcement.
  - supported:
    - MCAR/MAR/MNAR null injection,
    - `format_error` token mutation,
    - lag-based `stale_value`,
    - cumulative `drift` for numeric/date/datetime columns.
- Updated project JSON IO in `src/schema_project_io.py`:
  - load/save now preserves `data_quality_profiles` with shape checks on load.
- Added GUI project-level authoring support:
  - `src/gui_schema_core.py` now includes `Data quality profiles JSON (optional)` entry + JSON editor and parser.
  - `src/gui_schema_editor_base.py` includes the same control in native v2 layout and preserves the field in undo/load/projection flows.
- Preserved DG06 profile config across project-copy workflows:
  - `src/erd_designer.py`,
  - `src/performance_scaling.py`,
  - schema screen sample/project clone paths.
- Updated guide/docs:
  - `src/gui_tools/generation_guide_view.py`,
  - `DATA_SEMANTICS.md`,
  - `PROJECT_CANON.md`,
  - `GUI_WIREFRAME_SCHEMA.md`,
  - `NEXT_DECISIONS.md`.
- Added regression coverage:
  - new DG06 runtime/validation tests in `tests/test_missingness_quality_profiles.py`,
  - roundtrip test in `tests/test_schema_project_roundtrip.py`,
  - v2 GUI save/load metadata test in `tests/test_gui_v2_schema_project_generator_ui.py`,
  - invariant/guide assertions in `tests/test_invariants.py`.

## Consequences
- DG06 is opt-in and backward compatible: existing schemas remain valid without `data_quality_profiles`.
- Null and quality-defect realism can now be modeled in a deterministic, profile-driven way.
- Invalid DG06 profile definitions fail fast with actionable errors before or during generation.
