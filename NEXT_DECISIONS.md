## Active Direction
Direction 1 - Smarter Data

## Recent Completed Slice (Direction 1)
- Completed (2026-02-12): business-key attribute behavior controls added end-to-end:
  - table schema fields for `business_key_static_columns` and `business_key_changing_columns`,
  - validator rules for overlap/unknown/mismatch safeguards with actionable fix hints,
  - generator support so changing columns drive SCD2 mutations while static columns remain stable per business key,
  - GUI table editor controls in both `schema_project_legacy` and `schema_project`.

## Completed Direction
Direction 2 - Modular GUI Adoption (incremental, low-risk)
- Completed outcomes:
  - `schema_project` production route now uses `gui_kit` composition.
  - `schema_project_legacy` remains available as fallback route.
  - `schema_project_kit` remains available as modular parity reference route.

Direction 3 - Refactor float -> decimal; move semantic numeric types (lat/lon/money/percent) into generators.
- Completed outcomes:
  - first-class `decimal` in validation/generation/GUI/SQL IO with legacy `float` compatibility,
  - semantic numeric generators expanded (`money`, `percent`) alongside `latitude`/`longitude`,
  - default fixture/template schemas migrated from `float` to `decimal`,
  - GUI now blocks new `float` authoring (runtime validation) while preserving legacy JSON load/generate/export compatibility.
  - Float backward-compatibility tests ensure legacy schemas remain functional.
  - SCD options phase 2 completed: business key + SCD1/SCD2 table authoring/editing controls are now available in both schema designer screens, and example schema JSON includes SCD/business-key fields.
- Priority 1 completed (2026-02-12): canonical validator/runtime/GUI/test error wording is aligned to `<Location>: <issue>. Fix: <hint>.`

## In Progress
- CSV column sampling
- Extensible data types
- Realistic distributions
- DATA_SEMANTICS canonical spec adopted with migration notes for float compatibility
- GUI_WIREFRAME_SCHEMA canonical spec adopted for library-agnostic GUI design decisions and change tracking

## Next Candidates
**Priority 1 (future features):**
- Conditional generators (if/then)
- Time-aware constraints
- Hierarchical categories
- Validation heatmaps enhancements
- Extend SCD2 beyond current root-table-only scope (support incoming-FK child tables safely).

## Deferred
- Performance scaling
- Multiprocessing
- Full visual redesign

## New Extension Points
- `src/gui_kit/scroll.py`: `ScrollFrame`
- `src/gui_kit/panels.py`: `CollapsiblePanel`, `Tabs`
- `src/gui_kit/forms.py`: `FormBuilder`
- `src/gui_kit/table.py`: `TableView`
- `src/gui_kit/layout.py`: `BaseScreen`
- `src/gui_schema_project_kit.py`: reference modular screen using kit components
