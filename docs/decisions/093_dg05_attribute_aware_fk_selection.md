# 093 - DG05 Attribute-Aware FK Selection

## Context
- `NEXT_DECISIONS.md` prioritized DG05 to improve realism for parent-child relationship skew where uniform FK parent selection is not representative.
- Existing FK assignment only used uniform/random distribution within `min_children`/`max_children` bounds.
- DG05 required additive, deterministic behavior with schema validation, runtime enforcement, GUI authoring exposure, and regression coverage.

## Decision
- Extended FK contract in `src/schema_project_model.py`:
  - added optional `ForeignKeySpec.parent_selection` object.
  - validated `parent_selection.parent_attribute`, `weights`, and optional `default_weight` with canonical actionable errors.
  - blocked unsupported `bytes` parent attributes for cohort weighting.
- Implemented weighted FK assignment in `src/generator_project.py`:
  - added deterministic weighted count allocation helper that preserves per-parent `min_children`/`max_children` bounds.
  - single-FK and multi-FK paths now apply weighted selection when `parent_selection` is configured.
  - fallback behavior remains unchanged when `parent_selection` is absent.
- Added GUI authoring support in `src/gui_schema_core.py`:
  - relationships panel now includes optional `Parent selection JSON`.
  - add-relationship flow parses and validates JSON object shape before schema validation.
- Preserved FK profile during schema transformations:
  - table/column rename paths in `src/gui_schema_core.py` and `src/erd_designer.py` now carry `parent_selection` forward.
- Updated canonical docs and guide:
  - `DATA_SEMANTICS.md`, `PROJECT_CANON.md`, `GUI_WIREFRAME_SCHEMA.md`, `NEXT_DECISIONS.md`,
  - guide entry in `src/gui_tools/generation_guide_view.py`.
- Added regression tests:
  - `tests/test_attribute_aware_fk_selection.py`,
  - roundtrip preservation test in `tests/test_schema_project_roundtrip.py`,
  - v2 GUI parity coverage in `tests/test_gui_schema_project_v2_parity.py`.

## Consequences
- FK generation can now model parent cohort skew deterministically without violating cardinality constraints.
- Existing schemas remain backward compatible; DG05 is opt-in via `parent_selection`.
- Invalid FK weighting profiles fail fast with actionable location + fix hints.
