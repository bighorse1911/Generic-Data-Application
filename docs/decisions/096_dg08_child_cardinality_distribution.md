# 096 - DG08 Child-Cardinality Distribution Modeling

## Context
- `NEXT_DECISIONS.md` prioritized DG08 to extend FK child-count behavior beyond fixed min/max ranges with deterministic shape controls.
- Existing FK generation supported only min/max bounds (plus DG05 parent-selection weighting) and lacked an explicit child-count distribution contract.
- DG08 required additive behavior, deterministic generation, actionable validation/runtime errors, JSON roundtrip safety, and GUI relationship authoring exposure.

## Decision
- Extended FK schema contract in `src/schema_project_model.py`:
  - added optional `ForeignKeySpec.child_count_distribution`.
  - added DG08 validation for profile shape/semantics:
    - `type` in `uniform|poisson|zipf`,
    - `poisson` requires finite `lambda > 0`,
    - `zipf` requires finite `s > 0`.
- Implemented deterministic DG08 runtime behavior in `src/generator_project.py`:
  - normalized DG08 profile parsing for runtime safety.
  - added bounded distribution-weight compilation for `uniform`, `poisson`, and `zipf`.
  - integrated DG08 into single-FK and multi-FK assignment flows while preserving FK `min_children`/`max_children` constraints and FK integrity.
  - preserved DG05 interoperability by combining parent-selection weights with DG08 distribution-level weighting when both are configured.
- Updated GUI relationship authoring in `src/gui_schema_core.py` and `src/gui_schema_editor_base.py`:
  - added optional `Child count distribution JSON` FK input.
  - preserved DG08 values in FK copy/update flows.
  - surfaced DG08 summary labels in relationship tables for discoverability.
- Preserved DG08 FK metadata in related project-copy paths:
  - `src/erd_designer.py`.
- Updated generation guide content in `src/gui_tools/generation_guide_view.py` with a DG08 entry.
- Added/updated regression coverage:
  - `tests/test_child_cardinality_distribution.py` for determinism, bounds, multi-FK behavior, DG05+DG08 compatibility, and validation errors.
  - `tests/test_schema_project_roundtrip.py` for DG08 FK roundtrip persistence.
  - `tests/test_gui_schema_project_v2_parity.py` for v2 FK DG08 JSON persistence.
  - `tests/test_invariants.py` guide-entry assertions include DG08.

## Consequences
- DG08 is opt-in and backward compatible: existing schemas remain valid when `child_count_distribution` is absent.
- FK child-count behavior can now be shaped with deterministic distribution profiles while still honoring FK cardinality safety.
- DG05 weighted parent-cohort behavior remains available and composable with DG08.
- Invalid DG08 configuration fails fast with actionable location + fix-hint messaging.
