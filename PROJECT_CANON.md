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

## Architecture
- Tkinter GUI
- Pure-Python backend (no external deps)
- Schema-first design
- Generator registry pattern
- Reusable GUI kit layer (`src/gui_kit`) for modular screens:
  - `BaseScreen`: common screen behavior (`set_status`, `set_busy`, `safe_threaded_job`)
  - `ScrollFrame`: two-axis scrolling + mousewheel support
  - `CollapsiblePanel`: collapsible sections for large screens
  - `Tabs`: notebook wrapper for sectioned workflows
  - `FormBuilder`: consistent label+input row construction
  - `TableView`: Treeview wrapper with both scrollbars + column sizing

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
- Kit-based preview screen is additive and reachable from Home; legacy screen remains intact.

## Data Generation
- `ColumnSpec` drives generation
- Generators selected by `dtype` / `generator_id`
- Runtime dtypes today: int, decimal, float, text, bool, date, datetime.
- Direction 3 target dtypes: int, decimal, text, bool, date, datetime, bytes.
- Backward compatibility policy: existing `float` schema JSON remains supported during migration to `decimal`.
- All other semantics are generators. Refer to DATA_SEMANTICS.md for authoritative rules.
- Supports:
  - CSV sampling
  - Distributions (uniform, normal, lognormal)
  - Dates, timestamps, semantic numeric generators (lat/lon/money/percent)
  - Correlated columns via `depends_on`
- FK integrity enforced in-memory

## Validation
- `validate_project()` blocks invalid schemas
- FK integrity tests
- Defensive PK checks

## UX Principles
- Scrollable canvas
- Per-panel collapse
- No data loss on slow machines
- Preserve behavior while iterating UI in small, low-risk slices

## Non-Goals (for now)
- No external libraries
- No cloud deployment
