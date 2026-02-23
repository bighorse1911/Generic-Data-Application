# 089 - DG01 Correlated Column Groups

## Context
- `NEXT_DECISIONS.md` prioritized DG01 to improve joint realism beyond independent per-column generation.
- Existing correlation behavior relied on row-local `depends_on` logic, which did not provide matrix-driven multi-column rank-correlation control.
- DG01 required deterministic behavior, validation guardrails, JSON compatibility, and GUI authoring exposure before removing it from the backlog.

## Decision
- Extend `TableSpec` with optional `correlation_groups` configuration in `src/schema_project_model.py`.
- Implement validator guardrails for correlation groups:
  - required `group_id`, `columns`, and `rank_correlation`,
  - matrix shape/symmetry/range/diagonal checks,
  - positive-semi-definite matrix check,
  - disallow PK/incoming-FK/business-key/bytes columns,
  - disallow `depends_on` participation for grouped columns,
  - enforce one-group-per-column per table.
- Implement deterministic runtime correlation application in `src/generator_project.py`:
  - seeded per-table/per-group stochastic ranks,
  - rank-reordering that preserves each grouped column's marginal value multiset,
  - optional categorical ordering via `categorical_orders`,
  - optional blend factor via `strength`.
- Expose correlation-group authoring in schema GUI routes:
  - classic/legacy editor (`src/gui_schema_core.py`),
  - modular/v2 editor (`src/gui_schema_editor_base.py` and inherited `schema_project_v2`) via table-level JSON field + JSON editor dialog.
- Preserve/load/save compatibility:
  - JSON IO support in `src/schema_project_io.py`,
  - table-clone preservation updates in `src/performance_scaling.py` and `src/erd_designer.py`.

## Consequences
- DG01 is now an implemented feature, not a backlog candidate.
- Users can configure deterministic multi-column numeric/categorical rank-correlation without external dependencies.
- Validation is stricter around dependency interactions to prevent post-generation correlation rewrites from violating row-local dependency contracts.
- Added/updated regression coverage:
  - `tests/test_correlated_column_groups.py`,
  - `tests/test_schema_project_roundtrip.py`,
  - `tests/test_gui_v2_schema_project_generator_ui.py`.

