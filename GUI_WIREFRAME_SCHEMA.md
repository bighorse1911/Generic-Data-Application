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

## Implementation Status (2026-02-12)

- Current runtime GUI: Tkinter (`src/gui_home.py`)
- Production modular route: `schema_project` uses `src/gui_schema_project_kit.py` with `src/gui_kit`.
- Legacy fallback route: `schema_project_legacy` uses `src/gui_schema_project.py`.
- Direction 3 status: completed (`float` -> `decimal` migration and semantic numeric generator migration).
- SCD1/SCD2 support is implemented end-to-end (generator + validator + JSON IO + GUI authoring controls in both schema designer screens).
- Business-key behavior controls are implemented in both schema designer screens:
  - `business_key_static_columns` (stable attributes),
  - `business_key_changing_columns` (changing attributes).
- Column editor supports in-place editing of selected columns in addition to add/remove/reorder actions.
- GUI kit screens apply a shared dark-mode theme contract.
- Schema JSON path fields used by GUI flows (for example `sample_csv` params.path) prefer repo-root-relative references for portability.
- Home includes a dedicated route to a generation behaviors guide screen for in-app guidance.
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

Legacy compatibility:
- `float`: accepted at JSON schema load for backward compatibility; maps to decimal semantics at runtime.
  GUI validation **blocks** new columns with `dtype=float`; users must choose `decimal` instead.

Roadmap:
- `bytes`: binary payload (not yet implemented for GUI column creation; outside Direction 3 scope).

### 3.2 Error Format Contract

All GUI-surfaced validation errors must use this canonical shape:

- `<Location>: <issue>. Fix: <hint>.`

Where:
- `<Location>`: scope (table name / column name / panel name / etc.)
- `<issue>`: what is wrong
- `<hint>`: actionable fix

Examples:

- `Add column / Type: unsupported dtype 'foo'. Fix: choose one of: int, decimal, text, bool, date, datetime.`
- `Add column / Type: dtype 'float' is deprecated for new GUI columns. Fix: choose dtype='decimal' for new numeric columns; keep legacy float only in loaded JSON schemas.`
- `Table 'orders', column 'amount': min_value cannot exceed max_value. Fix: set min_value <= max_value.`

## 4. Current Screen Inventory (Authoritative Baseline)

### 4.1 `home`

- Purpose: entry navigation to available tools/screens.
- Required actions:
- open schema project designer (production modular route)
- open schema project designer kit route (modular parity reference path)
- open schema project designer legacy fallback route
- open generation behaviors guide screen

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
- schema validation summary + heatmap
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
- generator selector includes conditional generator option `if_then` (configured via Params JSON + depends_on)
- SCD configuration flow with mode selection (`scd1` or `scd2`) and business-key linkage.
- Business-key behavior controls: comma-separated static columns and changing columns, validated against existing table columns.
- SCD1 controls: tracked slowly-changing column selection.
- SCD2 controls: active period boundary columns (`from`/`to`, using `date` or `datetime`) plus tracked slowly-changing column selection.
- Uses `gui_kit` primitives (`BaseScreen`, `ScrollFrame`, `CollapsiblePanel`, `Tabs`, `FormBuilder`, `TableView`).

### 4.3 `schema_project_kit` (modular parity reference path)

- Mirrors modular production behavior for parity/regression checks.
- Uses `gui_kit` primitives (`BaseScreen`, `ScrollFrame`, `CollapsiblePanel`,
  `Tabs`, `FormBuilder`, `TableView`).
- Applies shared gui_kit dark-mode styling on page build.
- Additive navigation path from Home.
- Long-running actions on this screen (`Generate data`, `Generate sample`, `SQLite insert`) run via `BaseScreen.safe_threaded_job` to preserve busy/progress behavior and avoid duplicate-trigger races.

### 4.4 `schema_project_legacy` (fallback path)

- Purpose: low-risk fallback route while modular production path is adopted.
- Must preserve business-logic compatibility with modular production path for validation/generation/export/JSON IO flows.
- Uses pre-modular UI implementation from `src/gui_schema_project.py`.

### 4.5 `generation_behaviors_guide`

- Purpose: read-only, in-app reference that explains each generation behavior and how to configure it.
- Required regions:
- header with explicit back navigation to `home`
- scrollable content cards with "what it does" and "how to use" per behavior
- Required behavior:
- include core dtype-driven behavior, generator-driven behavior, depends_on/correlation behavior, and SCD/business-key table behavior notes
- content is instructional only (no schema mutation controls)
- navigation returns to `home` via Back button

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
