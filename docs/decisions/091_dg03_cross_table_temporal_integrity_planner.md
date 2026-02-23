# 091 - DG03 Cross-Table Temporal Integrity Planner

## Context
- `NEXT_DECISIONS.md` prioritized DG03 to improve realism for FK-linked event timelines.
- Existing generators handled row-local temporal logic (`time_offset`) but did not enforce cross-table temporal ordering bounds.
- DG03 required additive rollout with validator/runtime/JSON IO/GUI/doc/test parity and no external dependencies.

## Decision
- Added project-level optional field `SchemaProject.timeline_constraints`.
- Implemented validator coverage in `src/schema_project_model.py`:
  - project-level list/object shape validation,
  - unique `rule_id`,
  - one rule per `(child_table, child_column)`,
  - direct FK linkage enforcement via `via_child_fk`,
  - child/parent temporal dtype compatibility,
  - direction + offset bounds checks (`days` for `date`, `seconds` for `datetime`),
  - mode locked to `enforce`.
- Implemented runtime enforcement in `src/generator_project.py`:
  - compile constraints once per run,
  - enforce per table after FK assignment + correlation/SCD transforms and before table commit,
  - interval intersection across references,
  - preserve-valid / clamp-invalid / repair-null-or-unparseable child policy,
  - fail-fast runtime errors for missing parent mapping, unparseable parent temporal values, and empty intersections.
- Updated JSON IO in `src/schema_project_io.py`:
  - load + shape-check `timeline_constraints`,
  - preserve roundtrip through save (`asdict`).
- Preserved field through clone/rebuild sites:
  - `src/gui_schema_core.py`,
  - `src/gui_schema_editor_base.py`,
  - `src/erd_designer.py`,
  - `src/performance_scaling.py`.
- Added GUI authoring exposure:
  - project-level `Timeline constraints JSON (optional)` field + JSON editor action in schema authoring panels,
  - parser + actionable GUI error hints.
- Added generation guide entry:
  - `src/gui_tools/generation_guide_view.py`.
- Updated canonical docs:
  - `DATA_SEMANTICS.md`,
  - `PROJECT_CANON.md`,
  - `GUI_WIREFRAME_SCHEMA.md`,
  - `NEXT_DECISIONS.md`.

## Consequences
- Schemas can now enforce deterministic cross-table temporal integrity for chains like signup -> order -> ship -> invoice.
- DG03 remains opt-in and additive; schemas without `timeline_constraints` are unchanged.
- Invalid DG03 configuration fails fast at validation time with canonical actionable messages.
- Runtime enforces configured intervals deterministically without introducing external dependencies.
- Regression coverage expanded via:
  - new `tests/test_cross_table_temporal_integrity.py`,
  - roundtrip/UI/preservation/invariant updates in existing suites.

