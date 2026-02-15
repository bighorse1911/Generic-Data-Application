# Context
- Priority P5 in `NEXT_DECISIONS.md` required validation/error surfacing consistency across all interactive routes.
- Several interactive modules still mixed direct dialog calls with route-local formatting, which risked drift in actionable error shape and route title consistency.
- Hidden fallback routes needed the same error contract behavior as primary routes to keep rollback safe.

# Decision
- Added shared actionable error contract helpers in `src/gui_kit/error_contract.py`:
  - `ACTIONABLE_ERROR_PATTERN`
  - `format_actionable_error(...)`
  - `is_actionable_message(...)`
  - `coerce_actionable_message(...)`
- Extended `src/gui_kit/error_surface.py`:
  - warning support (`warning_title`, `show_warning`, `emit_warning(...)`)
  - actionable exception/warning coercion (`emit_exception_actionable(...)`, `emit_warning_actionable(...)`)
  - reusable dialog adapters (`show_error_dialog(...)`, `show_warning_dialog(...)`)
- Migrated interactive schema/tool modules off direct `messagebox.showerror/showwarning` usage:
  - `src/gui_schema_project.py`
  - `src/gui_schema_project_kit.py`
  - `src/gui_tools/erd_designer_view.py`
  - `src/gui_tools/location_selector_view.py`
- Standardized route-family titles:
  - Schema Project primary/kit: `Schema project error` / `Schema project warning`
  - Schema Project legacy: `Schema project legacy error` / `Schema project legacy warning`
  - ERD: `ERD designer error` / `ERD designer warning`
  - Location: `Location selector error` / `Location selector warning`
  - Performance Workbench: `Performance workbench error` / `Performance workbench warning`
  - Execution Orchestrator: `Execution orchestrator error` / `Execution orchestrator warning`
  - Run Center v2: `Run Center v2 error` / `Run Center v2 warning`
- Hardened run-screen exception paths to actionable coercion (`emit_exception_actionable(...)`) in:
  - `src/gui_home.py`
  - `src/gui_execution_orchestrator.py`
  - `src/gui_v2_redesign.py`
- Added regression coverage:
  - `tests/test_gui_kit_error_surface.py` (warning + actionable coercion behavior)
  - `tests/test_gui_error_surface_static_gate.py` (no direct `messagebox.showerror/showwarning` in migrated modules)
  - `tests/test_gui_error_surface_consistency.py` (route title matrix + read-only exclusions)
  - `tests/test_gui_error_contract_matrix.py` (representative actionable error/warning flows)

# Consequences
- Interactive routes now share one actionable error/warning surface with stable route-family titles and canonical fix-hint shape.
- Hidden fallback routes remain rollback-capable without drifting from primary error contract behavior.
- Read-only routes remain intentionally out of runtime error-surface plumbing scope for P5.
- Static and behavior regression gates reduce risk of direct dialog-call regressions in migrated modules.
