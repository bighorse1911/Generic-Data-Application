## Active Direction
Direction 1 - Smarter Data
Direction 2 - Modular GUI Adoption (incremental, low-risk)

## Completed Direction
Direction 3 - Refactor float -> decimal; move semantic numeric types (lat/lon/money/percent) into generators.
- Completed outcomes:
  - first-class `decimal` in validation/generation/GUI/SQL IO with legacy `float` compatibility,
  - semantic numeric generators expanded (`money`, `percent`) alongside `latitude`/`longitude`,
  - default fixture/template schemas migrated from `float` to `decimal`,
  - GUI now blocks new `float` authoring (runtime validation) while preserving legacy JSON load/generate/export compatibility.
  - Float backward-compatibility tests ensure legacy schemas remain functional.
  - SCD options phase 2 completed: business key + SCD1/SCD2 table authoring/editing controls are now available in both schema designer screens, and example schema JSON includes SCD/business-key fields.

## In Progress
- CSV column sampling
- Extensible data types
- Realistic distributions
- Reusable `gui_kit` layer for screen composition
- Kit-based Schema Project preview screen (additive navigation path from Home)
- DATA_SEMANTICS canonical spec adopted with migration notes for float compatibility
- GUI_WIREFRAME_SCHEMA canonical spec adopted for library-agnostic GUI design decisions and change tracking

## Next Candidates
**Priority 1 (unblocks others):**
- Align validator/runtime error wording across generator validation, GUI validation, and test output to match canonical error format from DATA_SEMANTICS section 8 and GUI_WIREFRAME_SCHEMA section 3.2: `<Location>: <issue>. Fix: <hint>.`

**Priority 2 (modular GUI migration):**
- Migrate additional screens to `gui_kit` components in small slices
- Standardize all form-heavy panels on `FormBuilder`
- Standardize all Treeview panels on `TableView`
- Convert long-running GUI actions to `BaseScreen.safe_threaded_job`

**Priority 3 (future features):**
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
