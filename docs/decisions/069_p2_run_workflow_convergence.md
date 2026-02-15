# Context
- Priority P2 in `NEXT_DECISIONS.md` required converging run workflows across `run_center_v2`, `performance_workbench`, and `execution_orchestrator`.
- Existing implementations duplicated lifecycle handling, run-control layout, error surfacing, and table plumbing across these screens.

# Decision
- Implemented shared run-workflow primitives in `src/gui_kit`:
  - `run_lifecycle.py` (`RunLifecycleState`, `RunProgressSnapshot`, `RunLifecycleController`, runtime/multiprocess event normalization)
  - `error_surface.py` (`actionable_error`, `ErrorSurface`)
  - `table_virtual.py` (`TableColumnSpec`, `VirtualTableAdapter`)
  - `run_models.py` (`RunWorkflowViewModel`, `coerce_output_mode`, `coerce_execution_mode`)
  - `run_commands.py` (shared adapters delegating to `performance_scaling` and `multiprocessing_runtime` canonical modules)
- Added shared run UI surface in `src/gui_tools/run_workflow_view.py`:
  - `RunWorkflowCapabilities`
  - `RunWorkflowSurface` (shared config/controls/progress/results-tabs sections with capability-gated actions/tabs)
- Migrated screens to shared architecture while preserving route keys and compatibility attributes:
  - `run_center_v2`
  - `performance_workbench`
  - `execution_orchestrator`
- Preserved behavior contracts: deterministic runtime behavior, existing validation semantics, actionable error contract, and backward-compatible JSON payload shapes.
- Kept run history visible only on `run_center_v2` in this slice.

# Consequences
- Run UX is now converged around one section model with reduced duplication and consistent lifecycle/error behavior.
- Existing route identities and invariant-required screen attributes remain stable for compatibility.
- Future P3+ work can extend shared patterns (and optional history rollout) without reintroducing per-screen drift.
