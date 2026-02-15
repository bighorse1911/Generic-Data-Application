# Generic Data Application - Project Canon

## Purpose
A GUI-driven synthetic data generator capable of producing realistic,
relational, schema-driven datasets for analytics, testing, and demos.

## Core Capabilities
- Multi-table schemas
- Multiple foreign keys per table
- Deterministic generation via seed
- CSV, SQLite output
- GUI schema designer
- GUI data generation behavior reference page
- GUI location selector page (map point/radius -> GeoJSON + deterministic lat/lon samples + CSV save)
- GUI ERD designer page (schema JSON -> entity relationship diagram with visibility toggles, draggable table layout, in-page schema/table/column/FK authoring including table/column edit, schema JSON export, and SVG/PNG/JPEG export)
- GUI performance workbench page (completed: schema load, performance profile validation, workload estimate diagnostics, deterministic FK-stage chunk-plan preview, runtime benchmark/generate flows with cancellation, profile save/load)
- GUI execution orchestrator page (completed: multiprocess config validation, FK-stage partition planning, worker monitor, retry/fallback controls, run-config save/load, and run-ledger save/load/recovery checks)
- GUI visual redesign routes (completed: `home_v2`, `schema_studio_v2`, `run_center_v2`, plus parity bridge routes `erd_designer_v2`, `location_selector_v2`, and `generation_behaviors_guide_v2`; includes v2 run-center runtime integration and schema-studio guarded navigation)

## Architecture
- Tkinter GUI
- Pure-Python backend (no external deps)
- Schema-first design
- Generator registry pattern
- GUI wireframe/design decision canon: `GUI_WIREFRAME_SCHEMA.md` (library-agnostic contract); all GUI design changes must update this file and add decision logs.
- Reusable GUI kit layer (`src/gui_kit`) for modular screens:
  - `BaseScreen`: common screen behavior (`set_status`, `set_busy`, `safe_threaded_job`) + `DirtyStateGuard` helpers for unsaved-change prompts
  - `ScrollFrame`: two-axis scrolling + mousewheel support
  - `CollapsiblePanel`: collapsible sections for large screens
  - `Tabs`: notebook wrapper for sectioned workflows
  - `FormBuilder`: consistent label+input row construction
  - `TableView`: Treeview wrapper with both scrollbars + column sizing + optional pagination controls
  - `ToastCenter`: non-blocking success/warn/error notifications
  - `SearchEntry`: deterministic debounce search input for list/table filtering
  - `TokenEntry`: chip-style editing for comma-separated column-name fields
  - `JsonEditorDialog`: formatted JSON editor with line/column parse feedback
  - `ShortcutManager`: centralized keyboard shortcuts + shortcuts help dialog
  - `ColumnChooserDialog`: modal column visibility + display-order chooser for table previews
  - `InlineValidationSummary`: inline validation issue list with jump-to-editor actions
  - `theme`: optional style helpers (kit screens now use regular/default platform theme)

## Screen Composition Standard
- New modular screens should split UI into dedicated section builders, not giant build methods.
- Current reference composition pattern:
  - `build_header()`
  - `build_project_panel()`
  - `build_tables_panel()`
  - `build_columns_panel()`
  - `build_relationships_panel()`
  - `build_generate_panel()`
  - `build_status_bar()`
- `schema_project` production route now uses the modular `gui_kit` composition path.
- Legacy pre-modular screen remains available as fallback route `schema_project_legacy` during transition.
- Home screen includes dedicated routes to a read-only generation behavior guide page, the ERD designer page, and the location selector page.
- Home screen includes a dedicated route to the performance workbench page.
- Home screen includes a dedicated route to the execution orchestrator page.
- Home screen includes a dedicated route to the full visual redesign experience (`home_v2`) with additive bridge routes for ERD/location/guide parity.
- Schema Studio v2 includes dirty-state guarded transitions when opening schema authoring routes.
- Run Center v2 includes integrated estimate/plan/benchmark/start controls wired to completed performance and multiprocessing runtime modules.
- ERD designer includes drag-to-reposition table nodes with relationship lines redrawn automatically.
- ERD designer includes export actions for SVG, PNG, and JPEG diagram outputs with actionable error guidance.
- ERD designer now supports in-page schema authoring for new schema creation, table creation/edit, column creation/edit (dtype + PK controls), FK relationship creation, and schema JSON export for downstream loading in schema designer routes.
- ERD designer schema authoring panel now supports collapse/expand and compact shared table/column save flows (blank selection = add new, selected item = edit existing).
- Column editor supports add, remove, move, and in-place edit of selected columns.
- Column editor now includes dtype-aware generator filtering, regex pattern presets, and generator params template fill assistance.
- Kit-based schema screen now includes debounced table/column/FK search controls, token-style editors for business-key column lists, non-blocking toast feedback, JSON params editor dialog, and a discoverable shortcuts help entry point.
- Kit-based schema screen now includes preview pagination, preview column visibility/order chooser, inline validation summary jump actions, and dirty-state guarded navigation/save prompts.
- Legacy fallback schema screen now includes low-risk Phase C adoption of Phase B UX primitives: opt-in preview pagination, preview column chooser, inline validation quick-jumps, and dirty-state guarded back/load prompts.
- Table editor now supports optional `business_key_unique_count` authoring so unique business-key count can be configured independently from table row count.
- GUI design changes must be recorded in `GUI_WIREFRAME_SCHEMA.md` and `docs/decisions/`.

## Data Generation
- `ColumnSpec` drives generation
- Generators selected by `dtype` / `generator_id`
- Direction 3 status: completed (`float` -> `decimal` migration and semantic numeric meaning moved to generators).
- Canonical authoring dtypes: `int`, `decimal`, `text`, `bool`, `date`, `datetime`, `bytes`.
- Legacy compatibility: `float` accepted at JSON load (maps to decimal semantics) and during export, but blocked at new column GUI creation.
- Runtime validation rejects `float` dtype in new column creation via GUI (invalid-dtype error); legacy float schemas remain load/generate/save compatible.
- Default fixture/template schemas are now authored with `decimal` for numeric non-integer fields.
- All other semantics are generators. Refer to DATA_SEMANTICS.md for authoritative rules.
- SCD semantics options are defined in DATA_SEMANTICS.md and implemented end-to-end:
  - SCD1 (business-key-linked overwrite-in-place with configurable tracked slowly-changing columns),
  - SCD2 (business-key-linked version rows with active period `date|datetime` and configurable tracked slowly-changing columns),
  - Business-key behavior controls support explicit static vs changing attribute column definitions.
  - Business-key cardinality supports optional `business_key_unique_count` per table (for example 200 unique keys across 2000 rows).
  - GUI authoring/editing controls for business key, business-key static columns, business-key changing columns, SCD mode, tracked columns, and SCD2 active-period columns are available in both schema designer screens.
- Supports:
  - Performance scaling runtime helpers (`src/performance_scaling.py`) for profile validation, deterministic workload diagnostics/planning, benchmark orchestration, and strategy-driven generation/export flows
  - Multiprocessing runtime helpers (`src/multiprocessing_runtime.py`) for execution-mode validation, deterministic FK-stage partition planning, worker orchestration events, retry/fallback handling, and run-ledger persistence checks
  - CSV sampling
  - CSV row-matched sampling (`sample_csv` optional `match_column` + `match_column_index` with `depends_on` for same-row linkage)
  - Repo-root-relative CSV sample paths in schema JSON (legacy absolute paths normalized when possible)
  - Conditional generators (phase 1 `if_then`)
  - Time-aware constraints (phase 2 `time_offset` with row-level date/datetime before/after offsets)
  - Hierarchical categories (phase 3 `hierarchical_category` with parent->children mapping)
  - Realistic distributions (uniform, normal, lognormal, weighted categorical) with validator/runtime guardrails and GUI authoring exposure
  - Ordered choices (`ordered_choice`) with named order paths and weighted movement progression
  - Dates, timestamps, semantic numeric generators (lat/lon/money/percent)
  - Extensible data type support: `bytes` (generated as binary payload, exported to CSV as base64 text, stored in SQLite as BLOB)
  - Correlated columns via `depends_on`
- Priority 1 phased rollout status: phases 1-5 are completed.
- FK integrity enforced in-memory

## Validation
- `validate_project()` blocks invalid schemas with actionable error format: `<Location>: <issue>. Fix: <hint>.`
- FK integrity tests
- Defensive PK checks
- GUI validation heatmap provides per-table buckets for PK, Columns, Dependencies, Generator, SCD/BK, and FKs.
- See DATA_SEMANTICS.md section 8 for canonical error contract

## UX Principles
- Scrollable canvas
- Per-panel collapse
- No data loss on slow machines
- Preserve behavior while iterating UI in small, low-risk slices

## Non-Goals (for now)
- No external libraries
- No cloud deployment
