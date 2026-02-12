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

## Architecture
- Tkinter GUI
- Pure-Python backend (no external deps)
- Schema-first design
- Generator registry pattern
- GUI wireframe/design decision canon: `GUI_WIREFRAME_SCHEMA.md` (library-agnostic contract); all GUI design changes must update this file and add decision logs.
- Reusable GUI kit layer (`src/gui_kit`) for modular screens:
  - `BaseScreen`: common screen behavior (`set_status`, `set_busy`, `safe_threaded_job`)
  - `ScrollFrame`: two-axis scrolling + mousewheel support
  - `CollapsiblePanel`: collapsible sections for large screens
  - `Tabs`: notebook wrapper for sectioned workflows
  - `FormBuilder`: consistent label+input row construction
  - `TableView`: Treeview wrapper with both scrollbars + column sizing
  - `theme`: shared dark-mode styling for kit-based screens

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
- Home screen includes a dedicated route to a read-only generation behavior guide page.
- Column editor supports add, remove, move, and in-place edit of selected columns.
- GUI design changes must be recorded in `GUI_WIREFRAME_SCHEMA.md` and `docs/decisions/`.

## Data Generation
- `ColumnSpec` drives generation
- Generators selected by `dtype` / `generator_id`
- Direction 3 status: completed (`float` -> `decimal` migration and semantic numeric meaning moved to generators).
- Canonical authoring dtypes: `int`, `decimal`, `text`, `bool`, `date`, `datetime`.
- Legacy compatibility: `float` accepted at JSON load (maps to decimal semantics) and during export, but blocked at new column GUI creation.
- Runtime validation rejects `float` dtype in new column creation via GUI (invalid-dtype error); legacy float schemas remain load/generate/save compatible.
- Future dtype extension candidate (outside Direction 3): `bytes`.
- Default fixture/template schemas are now authored with `decimal` for numeric non-integer fields.
- All other semantics are generators. Refer to DATA_SEMANTICS.md for authoritative rules.
- SCD semantics options are defined in DATA_SEMANTICS.md and implemented end-to-end:
  - SCD1 (business-key-linked overwrite-in-place with configurable tracked slowly-changing columns),
  - SCD2 (business-key-linked version rows with active period `date|datetime` and configurable tracked slowly-changing columns),
  - Business-key behavior controls support explicit static vs changing attribute column definitions.
  - GUI authoring/editing controls for business key, business-key static columns, business-key changing columns, SCD mode, tracked columns, and SCD2 active-period columns are available in both schema designer screens.
  Current limitation: `scd2` remains validated for root tables only (no incoming FKs).
- Supports:
  - CSV sampling
  - Repo-root-relative CSV sample paths in schema JSON (legacy absolute paths normalized when possible)
  - Conditional generators (phase 1 `if_then`)
  - Distributions (uniform, normal, lognormal)
  - Dates, timestamps, semantic numeric generators (lat/lon/money/percent)
  - Correlated columns via `depends_on`
- FK integrity enforced in-memory

## Validation
- `validate_project()` blocks invalid schemas with actionable error format: `<Location>: <issue>. Fix: <hint>.`
- FK integrity tests
- Defensive PK checks
- See DATA_SEMANTICS.md section 8 for canonical error contract

## UX Principles
- Scrollable canvas
- Per-panel collapse
- No data loss on slow machines
- Preserve behavior while iterating UI in small, low-risk slices

## Non-Goals (for now)
- No external libraries
- No cloud deployment
