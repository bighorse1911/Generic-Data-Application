# 081 - P12 Incremental Validation Engine

## Context
- Priority P12 in `NEXT_DECISIONS.md` required faster schema-validation feedback for large authoring workflows.
- Existing schema-route behavior revalidated the full project on each edit, which increased UI work for frequent table/column/FK changes.
- The P12 contract required preserving full-project validation before generate/export actions.

## Decision
- Implement a staged validation flow in `SchemaEditorBaseScreen` with:
  - debounced incremental execution (`VALIDATION_DEBOUNCE_MS`) for table/column/FK deltas,
  - scope expansion to related FK parent/child tables,
  - projected validation against scoped `SchemaProject` subsets,
  - cached issue merging so untouched-table validation state remains stable.
- Keep full-project validation as the explicit/manual path:
  - `Run validation` button and `F5` now execute full validation directly.
- Enforce full-project validation before generate/export actions:
  - generate all rows,
  - generate sample rows,
  - CSV export,
  - SQLite export.

## Consequences
- Authoring edits now avoid immediate full-project revalidation and coalesce repeated edits into one debounced pass.
- Validation summaries/heatmap/inline issue list remain consistent by merging scoped results with cached untouched-table results.
- Generate/export actions retain strict blocking behavior when full-project validation reports errors.
- Regression coverage in `tests/test_gui_incremental_validation.py` validates debounce behavior, scoped projection usage, and full-validation enforcement before generation.
