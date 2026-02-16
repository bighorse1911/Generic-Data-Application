# 074 - P7 Large-Data Responsiveness Pass

# Context
- Priority P7 in `NEXT_DECISIONS.md` required improving responsiveness for heavy table-refresh paths without changing data/runtime semantics.
- Core interactive routes still performed synchronous per-row `Treeview.insert(...)` loops in several high-volume refresh paths.
- Constraints required low-risk additive changes, no external dependencies, and legacy parity on hidden rollback routes.

# Decision
- Extended `src/gui_kit/table.py` (`TableView`) with shared large-data behavior:
  - configurable large-data mode (`configure_large_data_mode(...)`),
  - chunked non-blocking render pump (`after(0)`),
  - pending-render cancellation (`cancel_pending_render()`),
  - read-only render-state signal (`is_rendering`),
  - optional `set_rows(..., non_blocking=...)`,
  - auto-paging policy support for large result sets.
- Extended `src/gui_kit/table_virtual.py` (`VirtualTableAdapter`) to pass through the above large-data controls.
- Updated shared run surface `src/gui_tools/run_workflow_view.py` to:
  - configure adapter-level large-data behavior by table type,
  - expose explicit bulk row setters (`set_diagnostics_rows`, `set_plan_rows`, `set_worker_rows`, `set_failures_rows`, `set_history_rows`),
  - make `clear_tree(...)` adapter-aware so pending render jobs are cancelled safely.
- Migrated in-scope run routes to bulk row-set APIs:
  - `performance_workbench` (`src/gui_home.py`),
  - `execution_orchestrator` (`src/gui_execution_orchestrator.py`),
  - `run_center_v2` (`src/gui_v2_redesign.py`).
- Applied schema preview parity by enabling shared large-data chunking on preview tables in:
  - `schema_project` (`src/gui_schema_project_kit.py`),
  - `schema_project_legacy` (`src/gui_schema_project.py`),
  while preserving explicit/opt-in paging semantics per route.

# Consequences
- Large row refreshes no longer require monolithic synchronous `Treeview` population in primary heavy routes.
- Run-result tables now auto-page at large row counts (route layouts unchanged; no new paging controls introduced).
- Schema preview routes gain chunked refresh responsiveness while retaining their existing paging UX contracts.
- Added targeted tests for large-data table rendering/cancellation, adapter passthroughs, run-surface convergence contracts, and route-level P7 responsiveness scenarios.

# Rollback Notes
- Rollback can be performed by disabling large-data mode per table/adapter call site while keeping API-compatible code paths intact.
- New APIs are additive and optional; existing callers can continue using synchronous default behavior.
