# GUI Wireframe Schema
Generic Data Application

This document defines the canonical, library-agnostic GUI wireframe schema for
this project. It is authoritative for:

- screen topology and navigation
- panel composition and layout intent
- control semantics and data bindings
- validation and error presentation in GUI flows
- long-running action behavior (busy/progress/disable policy)
- GUI decision governance and update process

If GUI behavior is unclear, this document and `PROJECT_CANON.md` override
ad-hoc assumptions.

## Implementation Status (2026-02-15)

- Current runtime GUI: Tkinter (`src/gui_home.py`)
- Production modular route: `schema_project` uses `src/gui_schema_project_kit.py` with `src/gui_kit`.
- Hidden legacy rollback fallback route: `schema_project_legacy` uses `src/gui_schema_project.py` and is deprecated for one release cycle.
- Direction 3 status: completed (`float` -> `decimal` migration and semantic numeric generator migration).
- SCD1/SCD2 support is implemented end-to-end (generator + validator + JSON IO + GUI authoring controls in both schema designer screens).
- Business-key behavior controls are implemented in both schema designer screens:
  - `business_key_static_columns` (stable attributes),
  - `business_key_changing_columns` (changing attributes).
- Column editor supports in-place editing of selected columns in addition to add/remove/reorder actions.
- GUI kit screens use the regular/default Tk/ttk theme (dark mode is not forced).
- Schema JSON path fields used by GUI flows (for example `sample_csv` params.path) prefer repo-root-relative references for portability.
- Home includes a dedicated route to a generation behaviors guide screen for in-app guidance.
- Priority 1 phase 2 implemented: column generator selector now includes `time_offset` for time-aware date/datetime constraints using `depends_on` + params JSON.
- Priority 1 phase 3 implemented: column generator selector now includes `hierarchical_category` for parent->child category mapping constraints.
- Priority 1 phase 4 implemented: schema validation heatmap now includes explicit `Dependencies` and `SCD/BK` check buckets.
- Priority 1 phase 5 implemented: SCD2 validation/authoring now supports root and incoming-FK child tables.
- Priority 1 rollout status: phases 1-5 are completed.
- Extensible data types update: GUI dtype authoring now includes `bytes`.
- Realistic distributions update: column generator selector includes `uniform_int`, `uniform_float`, `normal`, `lognormal`, and `choice_weighted`.
- Ordered choices update: column generator selector includes `ordered_choice` with params JSON authoring support for multi-order progression behavior.
- GUI authoring ergonomics update: generator selector options are filtered by selected dtype, pattern presets are available for regex fields, and generator params template fill is available in column editor.
- GUI kit modernization phase A update: modular schema screen now uses debounced search controls (tables/columns/FKs), token-style editors for comma-separated business-key fields, non-blocking toasts for success feedback, params JSON editor dialog with parse location hints, and centralized shortcuts + help dialog.
- GUI kit modernization phase B update: modular schema screen now uses preview pagination, preview column visibility/order chooser, inline validation summary with jump actions, and dirty-state prompts for unsaved navigation/load flows.
- GUI kit modernization phase C update: legacy fallback screen now includes low-risk adoption of Phase B UX patterns (opt-in preview pagination, preview column chooser, inline validation jumps, dirty-state prompts).
- Business-key cardinality update: table editor now exposes optional `business_key_unique_count` to configure unique business keys separately from table row count.
- `sample_csv` authoring update: params JSON now supports optional dependent CSV sampling via `match_column` + `match_column_index` (with `depends_on` linkage).
- Location selector update: Home now routes to `location_selector` for map zoom/pan, point selection, radius-based GeoJSON output, and deterministic sample lat/lon preview.
- Location selector update: sample lat/lon output now includes one-click CSV save action.
- ERD designer update: Home now routes to `erd_designer` for schema JSON to ERD rendering with relationship/column/dtype visibility toggles.
- ERD designer update: ERD preview now includes export actions for SVG/PNG/JPEG output with actionable validation errors.
- ERD designer update: table nodes can now be dragged to reposition the diagram and relationships auto-redraw to match moved nodes.
- ERD designer update: page now includes in-place schema authoring controls for creating a new schema, adding tables, adding columns (dtype + PK), and adding FK relationships.
- ERD designer update: page now supports schema JSON export and in-place edit controls for existing tables and columns.
- ERD designer update: schema authoring panel is collapsible and table/column add+edit controls are compacted into shared save workflows.
- Performance scaling phase-1 update: Home now routes to `performance_workbench` for schema-linked performance profile validation and workload estimate diagnostics.
- Performance scaling phase-1B update: `performance_workbench` now includes deterministic FK-stage chunk-plan preview from profile settings.
- Performance scaling phase-1C update: `performance_workbench` now includes benchmark/generate runtime actions with cancellation and live progress metrics, plus CSV/SQLite strategy output integration.
- Multiprocessing feature update: Home now routes to `execution_orchestrator` for multiprocess configuration, FK-stage partition planning, worker monitoring, retry/fallback handling, and run-config persistence.
- Full visual redesign feature completion update: Home now routes to fully integrated v2 screens (`home_v2`, `schema_studio_v2`, `run_center_v2`) plus native specialist routes (`erd_designer_v2`, `location_selector_v2`, `generation_behaviors_guide_v2`).
- Native v2 parity update: hidden rollback fallback routes (`erd_designer_v2_bridge`, `location_selector_v2_bridge`, `generation_behaviors_guide_v2_bridge`) remain temporarily available for release-safety rollback.
- Full visual redesign core update: `schema_studio_v2` now applies dirty-state guarded navigation for schema route transitions; `run_center_v2` now integrates estimate/plan/benchmark/multiprocess execution flows using canonical runtime modules.
- Run workflow convergence update: `run_center_v2`, `performance_workbench`, and `execution_orchestrator` now share one run-workflow section model (config panel, run controls, progress strip, results tabs) with capability-gated tabs/actions and shared lifecycle/error/table primitives.
- Schema route consolidation update: `schema_project` is the only primary schema authoring route in Home and `schema_studio_v2`; hidden fallback routes remain `schema_project_kit` (alias) and deprecated `schema_project_legacy` (rollback only).
- Async lifecycle consistency update: shared teardown-safe UI dispatch now backs run-screen terminal callbacks and modular schema long jobs; legacy schema fallback includes blocker-level teardown-safe callback guards.
- Validation/error surface consistency update: interactive routes now route blocking errors and warnings through shared `ErrorSurface` pathways with canonical actionable shape and route-standardized titles; read-only routes are explicitly out of runtime error-plumbing scope.
- This schema is now the definitive place to record GUI design decisions so
  future library migrations can preserve behavior contracts.

## 1. GUI Invariants

These must hold regardless of GUI library:

1. Navigation must remain stable and explicit between screens.
2. GUI must not alter deterministic generation semantics (`project.seed`).
3. GUI must surface actionable validation/errors with location + fix hint.
4. Long-running operations must expose busy/progress state and prevent
   duplicate actions.
5. Scrollable layouts must support large schemas without hiding controls.
6. Existing JSON project load/save behavior remains backward compatible.

## 2. Wireframe Schema Model

All GUI decisions should be captured using the following schema concepts.

### 2.1 ScreenSpec

- `screen_id` (required): stable identifier (for example `schema_project`)
- `route_key` (required): navigation key used by app shell
- `title` (required): user-visible title
- `purpose` (required): short functional statement
- `regions` (required): ordered list of top-level regions/panels
- `actions` (required): user-triggered operations
- `validations` (required): GUI-level validation contracts
- `states` (required): loading/ready/error and disable rules
- `navigation` (required): inbound/outbound transitions
- `notes` (optional): migration or implementation notes

### 2.2 RegionSpec

- `region_id` (required): stable id
- `label` (required): user-visible region title
- `kind` (required): `header|panel|tabs|table|status_bar|dialog`
- `order` (required): integer display order
- `children` (optional): nested regions/components
- `collapse` (optional): `none|default_open|default_closed`
- `scroll` (optional): `none|x|y|xy`

### 2.3 ControlSpec

- `control_id` (required): stable id
- `kind` (required): `entry|combo|check|button|list|tree|progress|label`
- `bind` (optional): model/variable binding name
- `enabled_when` (optional): declarative state condition
- `valid_values` (optional): enumerated values for combos/selectors
- `on_action` (optional): callback/event contract
- `error_surface` (optional): `inline|dialog|status|mixed`

### 2.4 ValidationSpec

- `validation_id` (required): stable id
- `scope` (required): `project|table|column|fk|panel`
- `trigger` (required): `on_change|on_submit|on_generate|manual`
- `error_format` (required): must include location + issue + fix hint
- `blocking` (required): `true|false`

### 2.5 StateSpec

- `state_id` (required): `ready|running|error|disabled` (or equivalent)
- `entry_conditions` (required): when state activates
- `ui_effects` (required): controls disabled/enabled, progress behavior
- `exit_conditions` (required): completion/failure transitions

## 3. Canonical Data Types and Validation Error Contract

### 3.1 Canonical GUI Data Types (Authoritative Dtype List)

These dtypes are valid for new column creation in the GUI:
- `int`: whole numbers (signed)
- `decimal`: decimal numeric domain (non-integer, money, coordinates, rates)
- `text`: arbitrary text (names, labels, emails, UUIDs, etc. via generators)
- `bool`: boolean (true/false)
- `date`: calendar date (YYYY-MM-DD)
- `datetime`: timestamp with date+time (ISO 8601 string)
- `bytes`: binary payload (generated as bytes, exported as base64 text for CSV)

Legacy compatibility:
- `float`: accepted at JSON schema load for backward compatibility; maps to decimal semantics at runtime.
  GUI validation **blocks** new columns with `dtype=float`; users must choose `decimal` instead.

### 3.2 Error Format Contract

All GUI-surfaced validation errors must use this canonical shape:

- `<Location>: <issue>. Fix: <hint>.`

Where:
- `<Location>`: scope (table name / column name / panel name / etc.)
- `<issue>`: what is wrong
- `<hint>`: actionable fix

Examples:

- `Add column / Type: unsupported dtype 'foo'. Fix: choose one of: int, decimal, text, bool, date, datetime, bytes.`
- `Add column / Type: dtype 'float' is deprecated for new GUI columns. Fix: choose dtype='decimal' for new numeric columns; keep legacy float only in loaded JSON schemas.`
- `Table 'orders', column 'amount': min_value cannot exceed max_value. Fix: set min_value <= max_value.`

P5 standardization rules:
- Blocking errors and non-blocking warnings both use the same actionable contract (`<Location>: <issue>. Fix: <hint>.`).
- Route families use standardized dialog titles:
  - Schema project: `Schema project error` / `Schema project warning`
  - Schema project legacy: `Schema project legacy error` / `Schema project legacy warning`
  - ERD designer: `ERD designer error` / `ERD designer warning`
  - Location selector: `Location selector error` / `Location selector warning`
  - Performance workbench: `Performance workbench error` / `Performance workbench warning`
  - Execution orchestrator: `Execution orchestrator error` / `Execution orchestrator warning`
  - Run Center v2: `Run Center v2 error` / `Run Center v2 warning`
- Read-only routes are excluded from runtime error-surface wiring in this slice:
  - `home`, `home_v2`, `schema_studio_v2`, `generation_behaviors_guide`, `generation_behaviors_guide_v2`, and `*_v2_bridge` fallback routes.

## 4. Current Screen Inventory (Authoritative Baseline)

### 4.1 `home`

- Purpose: entry navigation to available tools/screens.
- Required actions:
- open schema project designer (production modular route)
- open generation behaviors guide screen
- open ERD designer screen
- open location selector screen
- open performance workbench screen
- open execution orchestrator screen
- open visual redesign preview home (`home_v2`)

### 4.2 `schema_project` (production modular path)

- Composition standard:
- `build_header()`
- `build_project_panel()`
- `build_tables_panel()`
- `build_columns_panel()`
- `build_relationships_panel()`
- `build_generate_panel()`
- `build_status_bar()`
- Required regions:
- project metadata and JSON save/load
- schema validation summary + heatmap (`PK`, `Columns`, `Dependencies`, `Generator`, `SCD/BK`, `FKs`)
- inline validation summary panel with jump-to-location actions
- table editor
- column editor + columns table
- FK relationship editor + FK table
- generation/preview/export/sqlite panel
- status line
- Required behavior:
- validation gating for generation buttons
- busy/progress during generation/export tasks via `BaseScreen.safe_threaded_job`
- actionable error dialogs for invalid actions
- column editor allows editing the selected column and validates edits before apply
- generator selector includes conditional/time-aware/hierarchical options `if_then`, `time_offset`, `hierarchical_category`, ordered-sequence option `ordered_choice`, plus distribution/weighted options `uniform_int`, `uniform_float`, `normal`, `lognormal`, and `choice_weighted` (configured via Params JSON + depends_on where applicable)
- generator selector list is filtered by selected dtype and blocks invalid dtype/generator combinations in column apply actions.
- regex field includes pattern preset controls for common patterns while still supporting custom regex input.
- generator params JSON includes template-fill action to reduce manual JSON authoring.
- generator params JSON supports a dedicated editor dialog with pretty-format and actionable parse error location (`line`, `column`).
- `sample_csv` params JSON supports optional dependent sampling (`match_column`, `match_column_index`) and relies on Depends on column linkage for same-row correlation.
- SCD configuration flow with mode selection (`scd1` or `scd2`) and business-key linkage.
- Business-key behavior controls: token-style comma-separated static/changing/business-key column editors, validated against existing table columns.
- Table editor includes optional unique business-key count (`business_key_unique_count`) to support scenarios where generated row count exceeds unique business keys.
- SCD1 controls: tracked slowly-changing column selection.
- SCD2 controls: active period boundary columns (`from`/`to`, using `date` or `datetime`) plus tracked slowly-changing column selection; applies to root and incoming-FK child tables.
- Includes discoverable keyboard shortcuts help and debounced search controls for large schema navigation.
- Preview table supports paged rendering for large row previews.
- Preview supports a column chooser dialog for visibility and display-order control without mutating schema column order.
- Screen-level dirty-state behavior prompts on unsaved back/load navigation and exposes an unsaved indicator.
- Uses `gui_kit` primitives (`BaseScreen`, `ScrollFrame`, `CollapsiblePanel`, `Tabs`, `FormBuilder`, `TableView`, `ColumnChooserDialog`, `InlineValidationSummary`).

### 4.3 `schema_project_kit` (hidden alias fallback path)

- Hidden fallback route alias to the same screen instance as `schema_project`.
- Uses `gui_kit` primitives (`BaseScreen`, `ScrollFrame`, `CollapsiblePanel`,
  `Tabs`, `FormBuilder`, `TableView`, `ColumnChooserDialog`, `InlineValidationSummary`).
- Uses default platform theme styling (no forced dark mode).
- Not a primary navigation target from Home or `schema_studio_v2`.
- Long-running actions on this screen (`Generate data`, `Generate sample`, `SQLite insert`) run through shared `gui_kit.job_lifecycle.JobLifecycleController` with `BaseScreen.safe_threaded_job` dispatch to preserve busy/progress behavior and avoid duplicate-trigger races.
- Thread->UI callback dispatch for long-running actions must be teardown-safe (drop callbacks silently when widget/root is no longer alive).

### 4.4 `schema_project_legacy` (deprecated hidden rollback path)

- Purpose: temporary hidden rollback fallback for one release cycle while consolidated modular route remains primary.
- Must preserve business-logic compatibility with modular production path for validation/generation/export/JSON IO flows.
- Uses pre-modular UI implementation from `src/gui_schema_project.py`.
- Not a primary navigation target from Home or `schema_studio_v2`.
- Includes low-risk Phase C adoption of selected gui_kit components:
  - `TableView` for preview table rendering with opt-in pagination controls,
  - `ColumnChooserDialog` for preview column visibility/order,
  - `InlineValidationSummary` panel with quick-jump actions,
  - dirty-state prompts for unsaved back/load navigation.
- Legacy async worker callbacks must use teardown-safe scheduling guards to avoid uncaught `_tkinter.TclError` during shutdown/destruction.

### 4.5 `generation_behaviors_guide`

- Purpose: read-only, in-app reference that explains each generation behavior and how to configure it.
- Required regions:
- header with explicit back navigation to `home`
- scrollable content cards with "what it does" and "how to use" per behavior
- Required behavior:
- include core dtype-driven behavior, generator-driven behavior, depends_on/correlation behavior, and SCD/business-key table behavior notes
- content is instructional only (no schema mutation controls)
- navigation returns to `home` via Back button

### 4.6 `location_selector`

- Purpose: map-based geographic selection utility for authoring center+radius area definitions.
- Required regions:
- header with explicit back navigation to `home`
- interactive map canvas with zoom and pan controls
- selection controls (center latitude/longitude, radius km, GeoJSON resolution, deterministic sample count/seed)
- GeoJSON output preview panel
- sample latitude/longitude output preview panel
- sample latitude/longitude CSV save action
- status line
- Required behavior:
- left-click map selects center point and updates latitude/longitude fields
- map supports basic navigation actions (zoom in/out, wheel zoom, pan drag, reset view)
- Build GeoJSON action validates center/radius/resolution and emits a polygon GeoJSON circle
- Generate sample points action emits deterministic latitude/longitude samples bounded by selected radius
- Save points CSV action writes generated sample points to a user-selected CSV path
- validation/errors use actionable `<Location>: <issue>. Fix: <hint>.` messaging
- output panels are read-only previews intended for downstream copy/use in future geographic workflows

### 4.7 `erd_designer`

- Purpose: render entity relationship diagrams from schema project JSON input for structure review and communication.
- Required regions:
- header with explicit back navigation to `home`
- schema input controls (path entry + browse + render action + ERD export action + schema JSON export action)
- schema authoring controls (new schema name/seed, compact shared add/edit table + column controls, add relationship) with collapse/expand toggle
- ERD visibility controls (show relationships, show column names, show datatypes)
- scrollable ERD canvas
- status line
- Required behavior:
- loads schema input from project JSON using existing schema IO contracts
- renders table nodes and FK relationships deterministically from schema content
- supports display toggles for relationships, columns, and datatypes without mutating schema data
- supports drag-and-drop table-node repositioning within ERD canvas
- relationship lines/labels update automatically when connected tables are moved
- supports in-page schema authoring without leaving `erd_designer`:
  - create a new empty schema project (name + seed),
  - add/edit tables with row-count hints via shared save controls (blank table selection adds new; selected table updates existing),
  - add/edit columns with canonical GUI dtypes and PK/nullability controls via shared save controls (blank column selection adds new; selected column updates existing),
  - add FK relationships with child/parent mapping and min/max children.
- supports collapsing schema authoring panel so ERD canvas review can use more vertical space.
- supports schema project JSON export from the authored ERD state for downstream load in schema designer flows.
- supports ERD export to `.svg`, `.png`, `.jpg`, and `.jpeg`
- SVG export uses current moved node positions from the interactive layout
- raster export surfaces actionable errors if required conversion tooling is unavailable
- uses actionable `<Location>: <issue>. Fix: <hint>.` error messaging for invalid/missing schema input

### 4.8 `performance_workbench`

- Purpose: completed performance scaling workbench using the shared run-workflow surface for planning, benchmark, and strategy-driven generation/export.
- Required regions:
- header with explicit back navigation to `home`
- shared run config panel:
  - schema input controls
  - workload profile controls
  - execution strategy controls
  - profile save/load controls
- shared run controls strip (capability-gated actions)
- shared progress strip (progress bar + phase/status + rows + ETA/throughput)
- shared results tab host with capability tabs:
  - diagnostics tab (`table`, estimated rows/memory/write/time, risk, recommendation)
  - chunk plan tab (`table`, `stage`, `chunk`, `start_row`, `end_row`, `rows`)
- status line
- Capability matrix (enabled actions/tabs):
- actions: `estimate`, `build plan`, `benchmark`, `generate(strategy)`, `cancel`
- tabs: `diagnostics`, `plan`
- omitted in this route: `workers`, `failures`, `history`
- Required behavior:
- uses shared lifecycle/state handling for start/cancel/progress/complete/failure transitions
- runtime terminal callbacks and event marshalling use teardown-safe UI dispatch so callback scheduling is dropped safely if the UI host is destroyed
- profile fields validate with actionable `<Location>: <issue>. Fix: <hint>.` errors before estimate run
- row override validation enforces existing-table keys and FK minimum-row guardrails
- strict deterministic chunking cannot be disabled while deterministic generation contract is required
- estimate action computes deterministic per-table diagnostics from loaded schema + profile
- diagnostics tab updates in-place and status line reports aggregated summary
- build plan action computes deterministic FK-stage-aware table chunk ranges and renders chunk table preview
- build plan action rejects cyclic selected-table FK dependency graphs with actionable fix-hint errors
- run benchmark action emits live progress updates while evaluating chunk-plan execution flow
- generate with strategy action runs deterministic generation using selected profile and supports output modes (`preview|csv|sqlite|all`)
- cancel action signals runtime cancellation and returns UI to ready state without blocking the main thread
- CSV strategy mode writes one CSV per selected/required table using buffered row writes
- SQLite strategy mode creates tables and inserts rows using configured batch size
- profile save/load uses JSON object payload and re-validates loaded values before apply

### 4.9 `execution_orchestrator`

- Purpose: completed multiprocessing execution planner/runner using the shared run-workflow surface for staged partition monitoring with retry/fallback controls.
- Required regions:
- header with explicit back navigation to `home`
- shared run config panel:
  - schema input controls
  - workload profile controls
  - execution mode controls
  - run-config save/load controls
- shared run controls strip (capability-gated actions)
- shared progress strip (progress bar + phase/status + rows + ETA/throughput)
- shared results tab host with capability tabs:
  - partition plan tab (`table`, `partition_id`, `row range`, `stage`, `assigned worker`, `status`)
  - worker monitor tab (`worker`, current table/partition, rows, throughput, memory, heartbeat, state)
  - failures tab (`partition_id`, `error`, `retry_count`, `action`)
- status line
- Capability matrix (enabled actions/tabs):
- actions: `build plan`, `start`, `start+fallback`, `cancel`
- tabs: `plan`, `workers`, `failures`
- omitted in this route: `diagnostics`, `history`
- Required behavior:
- uses shared lifecycle/state handling for start/cancel/progress/complete/failure transitions
- runtime terminal callbacks and event marshalling use teardown-safe UI dispatch so callback scheduling is dropped safely if the UI host is destroyed
- execution mode fields validate with actionable `<Location>: <issue>. Fix: <hint>.` errors before plan/run
- worker count must respect mode/platform bounds (`single_process` requires worker_count=1; multiprocess count must be <= CPU count)
- max inflight and queue size must remain capacity-safe (`max_inflight_chunks >= worker_count`, `ipc_queue_size >= max_inflight_chunks`)
- build plan action computes deterministic FK-stage partition assignments and worker allocation
- start action executes staged partition workers and emits live progress events to status/monitor panels
- retry behavior uses configured `retry_limit`; failures are listed in failure panel with actionable recovery hints
- start-with-fallback action switches to deterministic single-process strategy run if multiprocess partition execution exhausts retries
- cancel action requests cancellation and returns UI to ready state without blocking the main thread
- run-config save/load uses JSON object payload and re-validates loaded values before apply

### 4.10 `home_v2`

- Purpose: entry screen for the completed visual redesign route set while preserving classic-home access.
- Required regions:
- header with explicit back navigation to `home`
- primary route cards for `schema_studio_v2` and `run_center_v2`
- specialist route cards for `erd_designer_v2`, `location_selector_v2`, and `generation_behaviors_guide_v2`
- Required behavior:
- additive route only; does not replace classic home routes
- visual redesign routes remain non-destructive and preserve canonical app behavior

### 4.11 `schema_studio_v2`

- Purpose: phased redesign shell for schema authoring workflow (`project|tables|columns|relationships|run` sections).
- Required regions:
- v2 shell header/action bar
- left navigation rail
- central workspace tabs
- right inspector panel
- bottom status strip
- Required behavior:
- section navigation updates selected workspace tab and inspector content
- route includes explicit navigation to `run_center_v2` and classic home
- schema section transitions (`project|tables|columns|relationships`) route to `schema_project` only
- schema transitions use dirty-state guarded navigation based on primary schema route dirty state
- hidden fallback routes (`schema_project_kit`, `schema_project_legacy`) remain rollback-only and are not primary section targets
- v2 page is navigation-first and does not change canonical data semantics

### 4.12 `run_center_v2`

- Purpose: redesign run-focused workflow and shared baseline for converged run UX across run screens.
- Required regions:
- v2 shell header/action bar
- left navigation rail
- shared run config card
- shared run controls strip (capability-gated actions)
- shared progress strip
- shared results tab host
- right inspector panel
- status strip
- Capability matrix (enabled actions/tabs):
- actions: `estimate`, `build plan`, `benchmark`, `start`, `start+fallback`, `cancel`
- tabs: `diagnostics`, `plan`, `failures`, `history`
- Required behavior:
- run config fields map to canonical performance and multiprocessing config parsers/validators
- uses shared lifecycle/state handling for start/cancel/progress/complete/failure transitions
- runtime terminal callbacks and event marshalling use teardown-safe UI dispatch so callback scheduling is dropped safely if the UI host is destroyed
- estimate action computes deterministic workload diagnostics and summary
- build plan action computes deterministic FK-stage partition plan preview
- benchmark action runs canonical performance benchmark flow with progress updates and cancellation
- start action runs canonical multiprocessing orchestration flow (including retry/fallback handling)
- history tab remains intentionally visible only on `run_center_v2` in the convergence scope
- config save/load uses JSON payload and rehydrates run-center form state

### 4.13 `erd_designer_v2`

- Purpose: native v2 ERD designer route for schema visualization, authoring, and export workflows.
- Required regions:
- v2 shell header/action bar
- left navigation rail (`erd tool`, `overview`)
- central native ERD tool workspace (shared canonical behavior contract)
- right inspector panel
- status strip
- Required behavior:
- supports schema JSON load/render, visibility toggles, drag table layout, in-page schema authoring/editing, schema JSON export, and SVG/PNG/JPEG export
- preserves canonical actionable error contract and deterministic rendering behavior
- additive route only; classic `erd_designer` remains available

### 4.14 `location_selector_v2`

- Purpose: native v2 location selector route for map/location workflows.
- Required regions:
- v2 shell header/action bar
- left navigation rail (`location tool`, `overview`)
- central native location tool workspace (shared canonical behavior contract)
- right inspector panel
- status strip
- Required behavior:
- supports map zoom/pan/click center selection, radius/GeoJSON generation, deterministic sample-point generation, and CSV save
- preserves canonical actionable error contract and deterministic sample behavior
- additive route only; classic `location_selector` remains available

### 4.15 `generation_behaviors_guide_v2`

- Purpose: native v2 read-only generation behavior guide route.
- Required regions:
- v2 shell header/action bar
- left navigation rail (`guide`, `overview`)
- central native guide workspace (shared canonical content)
- right inspector panel
- status strip
- Required behavior:
- renders canonical read-only behavior guide content without schema mutation controls
- additive route only; classic `generation_behaviors_guide` remains available

### 4.16 `*_v2_bridge` (rollback fallback routes)

- Purpose: temporary hidden rollback routes retained for one release cycle.
- Routes:
- `erd_designer_v2_bridge`
- `location_selector_v2_bridge`
- `generation_behaviors_guide_v2_bridge`
- Required behavior:
- provide launch-through fallback to corresponding classic production routes
- not primary navigation targets from `home_v2`
- removal is allowed after parity and regression gates are stable

## 5. Library-Agnostic Mapping Guide

When porting to another GUI library, preserve these semantic mappings:

- `ScreenSpec` -> framework screen/view/page
- `RegionSpec(kind=panel)` -> group box/card/section
- `ControlSpec(kind=entry|combo|check|button)` -> native form controls
- `ControlSpec(kind=tree)` -> table/grid widget with scrolling
- `StateSpec(state_id=running)` -> disable action controls + show progress
- `ValidationSpec(blocking=true)` -> prevent operation and show error surface

Implementation widgets may change; semantics must not.

## 6. Update Protocol (Required For GUI Changes)

For any GUI design decision, follow all steps:

1. Update this document (`GUI_WIREFRAME_SCHEMA.md`) with the new/changed
   ScreenSpec, RegionSpec, control contract, or state/validation rule.
2. Update `PROJECT_CANON.md` if architecture-level GUI rules changed.
3. Update `NEXT_DECISIONS.md` if roadmap status or candidates changed.
4. Add a new incremented file in `docs/decisions/` summarizing context,
   decision, and consequences.
5. Add/update tests when behavior changes.

## 7. Change Template

Use this template when documenting a new GUI design decision in this file:

```text
Change ID: gui-YYYYMMDD-short-name
Scope: screen_id / region_id / control_id
Reason: why the change is needed
Decision: what changed in wireframe schema terms
Behavioral impact: what users will observe
Compatibility: migration/backward-compatibility notes
Test impact: tests added or updated
```
