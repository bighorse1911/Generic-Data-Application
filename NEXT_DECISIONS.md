## Active Direction
Direction 1 - Smarter Data

## Recent Completed Slice (Direction 1)
- Completed (2026-02-14): ERD designer draggable layout added:
  - ERD table nodes can now be dragged to reposition entities directly on the canvas,
  - FK relationship lines and labels now redraw against the moved node positions automatically,
  - SVG export now respects moved node positions so exported diagrams match the interactive layout.
- Completed (2026-02-14): ERD designer export options added:
  - added `Export ERD...` action to save the rendered ERD as `.svg`, `.png`, `.jpg`, or `.jpeg`,
  - added deterministic SVG export from ERD layout data,
  - added actionable guardrails for invalid export formats/paths and missing raster conversion prerequisites.
- Completed (2026-02-14): ERD designer GUI page added:
  - added Home route `erd_designer`,
  - added schema JSON input + canvas ERD rendering for tables and foreign-key relationships,
  - added ERD display controls for relationships, column names, and datatypes.
- Completed (2026-02-14): Location selector CSV export action added:
  - added `Save points CSV...` action to persist generated location samples directly from the location selector screen,
  - added actionable guardrails when save is attempted before point generation or without a valid output path,
  - added utility/test coverage for deterministic CSV formatting/writes.
- Completed (2026-02-14): Location selector GUI page added:
  - added Home route `location_selector`,
  - added interactive Earth map page with zoom/pan, point selection, and radius-driven GeoJSON circle generation,
  - added deterministic latitude/longitude sample-point generation inside selected radius for downstream geographic authoring.
- Completed (2026-02-14): Dependent CSV sampling added for same-row column correlation:
  - `sample_csv` now supports optional params `match_column` + `match_column_index` to filter sampled values by another already-generated column in the same row,
  - validator/runtime guardrails enforce source-column existence, `depends_on` ordering, and actionable errors when CSV matches are unavailable,
  - generation behaviors guide text now documents dependent `sample_csv` setup in GUI flows.
- Completed (2026-02-12): GUI generation behavior guide page added:
  - added Home route `generation_behaviors_guide`,
  - added read-only screen documenting supported generation behaviors and setup patterns,
  - added GUI navigation contract assertions for the new screen.
- Completed (2026-02-12): Priority 1 phased rollout started with conditional generators phase 1:
  - added `if_then` generator for deterministic if/then branching from row context,
  - added validator guardrails for params shape and `depends_on` ordering requirements,
  - exposed `if_then` in GUI generator selection.
- Completed (2026-02-14): Priority 1 phase 2 time-aware constraints added:
  - added `time_offset` generator for deterministic row-level date/datetime before/after offsets from a source column,
  - added validator guardrails for source-column linkage, dtype compatibility, `depends_on` ordering, direction, and offset bounds,
  - exposed `time_offset` in GUI generator selection and generation behaviors guide content.
- Completed (2026-02-14): Priority 1 phases 3-5 completed:
  - Phase 3 hierarchical categories: added `hierarchical_category` generator with parent-column mapping semantics and validator/runtime guardrails.
  - Phase 4 validation heatmap enhancements: expanded schema heatmap buckets (Dependencies, SCD/BK) with richer per-table issue surfacing.
  - Phase 5 SCD2 child-table support: removed root-table-only validator restriction and added capacity-aware SCD2 version growth for incoming-FK child tables.
- Completed (2026-02-14): CSV column sampling finalized:
  - `sample_csv` generator + validator/runtime guardrails are active,
  - repo-root-relative JSON path portability and normalization are implemented,
  - fixture and guardrail tests cover missing-path, bad-column, and deterministic behavior paths.
- Completed (2026-02-14): Priority 1 phased rollout fully completed (phases 1-5):
  - phase 1 `if_then`,
  - phase 2 `time_offset`,
  - phase 3 `hierarchical_category`,
  - phase 4 validation heatmap enhancements,
  - phase 5 SCD2 support beyond root-table-only scope.
- Completed (2026-02-14): Canonical spec adoption finalized:
  - DATA_SEMANTICS canonical spec is adopted with float-compatibility migration notes,
  - GUI_WIREFRAME_SCHEMA canonical spec is adopted for library-agnostic GUI decisions/change tracking.
- Completed (2026-02-14): Extensible data types implemented:
  - promoted `bytes` from roadmap candidate to first-class dtype in validation, generation, GUI authoring, SQL DDL/SQLite paths, and tests,
  - added bytes export behavior for CSV (base64 text) and SQLite storage as BLOB.
- Completed (2026-02-14): Realistic distributions completed:
  - GUI column generator selector now includes `uniform_int`, `uniform_float`, `normal`, `lognormal`, and `choice_weighted`.
  - Validator guardrails now enforce distribution dtype compatibility and actionable params checks (bounds, variance/sigma positivity, weighted-choice shape/values).
  - Runtime distribution behavior now includes robust param errors, `normal` support for `stdev|stddev`, and optional `min|max` clamping for `lognormal`.
- Completed (2026-02-14): GUI generator authoring ergonomics update:
  - generator selector is now filtered by selected column dtype (shows only valid generators for that dtype),
  - column editor adds regex pattern presets for common cases,
  - column editor adds "Fill params template" action for generator params JSON bootstrapping.
- Completed (2026-02-14): GUI theme preference update:
  - removed forced dark mode application from kit-based schema designer screens,
  - restored regular/default Tk/ttk theme rendering for GUI surfaces.
- Completed (2026-02-14): Ordered choices generator behavior added:
  - added `ordered_choice` generator with multi-order path selection and weighted movement progression,
  - added validator guardrails for params shape (`orders`, `order_weights`, `move_weights`, `start_index`) with actionable fix hints,
  - exposed `ordered_choice` in GUI generator filtering and params template defaults.
- Completed (2026-02-14): Priority 1 GUI kit modernization phase A implemented:
  - added reusable `ToastCenter`, `SearchEntry`, `TokenEntry`, `JsonEditorDialog`, and `ShortcutManager` primitives in `src/gui_kit`,
  - integrated phase-A primitives into modular `schema_project` route (non-blocking toasts, debounced search controls, token editors, params JSON dialog, and shortcuts help),
  - added GUI-kit component and screen integration tests for the new primitives.
- Completed (2026-02-14): Priority 1 GUI kit modernization phase B implemented:
  - `TableView` now supports an opt-in pagination path for large preview row sets.
  - Added `ColumnChooserDialog` and integrated preview column visibility/order controls without mutating underlying schema column order.
  - Added `DirtyStateGuard` pattern in `BaseScreen` and integrated unsaved-change indicator + guarded back/load flows in modular schema screen.
  - Added `InlineValidationSummary` panel with jump actions to table/column/FK editor contexts.
  - Added phase-B unit/integration tests for pagination helpers, dirty-state flow, and validation jump behavior.
- Completed (2026-02-14): Priority 1 GUI kit modernization phase C legacy adoption implemented:
  - integrated Phase B components into `schema_project_legacy` in a low-risk slice,
  - added opt-in preview pagination + preview column chooser in legacy screen,
  - added legacy dirty-state prompts for back/load navigation with save/discard/cancel flow,
  - added inline validation summary jump actions to table/column/FK editing contexts,
  - added legacy Phase C tests and verified full regression suite remains green.
- Completed (2026-02-14): Business-key cardinality control implemented:
  - added optional table field `business_key_unique_count` to configure unique business keys separately from table `row_count`,
  - validator/runtime guardrails now enforce actionable errors for invalid combinations (`business_key` required, positive integer, row-count bounds, and SCD1 one-row-per-key semantics),
  - generation now supports scenarios like 200 unique business keys across 2000 rows while preserving deterministic seed behavior,
  - added table-editor controls in both legacy and kit screens and covered with regression tests.
- Completed (2026-02-12): CSV sampling path portability hardening:
  - schema/sample_csv paths now resolve relative to repo root,
  - legacy absolute fixture-style paths normalize to repo-relative form where possible,
  - load/save JSON paths now prefer `tests/...` style references for repo-local files.
- Completed (2026-02-12): GUI column editor + kit dark mode improvements:
  - added in-place selected-column editing flow in schema designer screens,
  - preserved validator-first safety checks and actionable GUI error wording,
  - added shared gui_kit dark-mode styling and applied it to kit-based pages.
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
- None currently.

## Next Candidates
**Priority 1 (future features):**
- None currently.

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
- `src/gui_kit/column_chooser.py`: `ColumnChooserDialog`
- `src/gui_kit/validation.py`: `InlineValidationSummary`
- `src/gui_schema_project_kit.py`: reference modular screen using kit components
