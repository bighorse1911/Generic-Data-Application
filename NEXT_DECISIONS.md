## Active Direction
Direction 1 - Smarter Data
Direction 2 - Modular GUI Adoption (incremental, low-risk)
Direction 3 - Refactor float -> decimal; move semantic numeric types (lat/lon/money/percent) into generators.

## In Progress
- CSV column sampling
- Extensible data types
- Realistic distributions
- Reusable `gui_kit` layer for screen composition
- Kit-based Schema Project preview screen (additive navigation path from Home)
- DATA_SEMANTICS canonical spec adopted with migration notes for float compatibility
- Direction 3 phase slice completed: first-class `decimal` in validation/generation/GUI/SQL IO with legacy `float` compatibility
- Semantic numeric generators expanded (`money`, `percent`) alongside `latitude`/`longitude`

## Next Candidates
- Align validator/runtime error wording to DATA_SEMANTICS actionable format (table, column, issue, fix hint)
- Direction 3 follow-on phases:
- Phase 3: migrate default fixtures/templates from `float` to `decimal`
- Phase 4: deprecate `float` authoring in GUI while preserving JSON load compatibility
- Migrate additional screens to `gui_kit` components in small slices
- Standardize all form-heavy panels on `FormBuilder`
- Standardize all Treeview panels on `TableView`
- Convert long-running GUI actions to `BaseScreen.safe_threaded_job`
- Conditional generators (if/then)
- Time-aware constraints
- Hierarchical categories
- Validation heatmaps enhancements

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
