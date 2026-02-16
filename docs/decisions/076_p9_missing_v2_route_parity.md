# 076 - P9 Native V2 Route Parity For Missing GUI Components

Date: 2026-02-16

## Context
- After P8, native v2 coverage existed for `home_v2`, `schema_studio_v2`, `run_center_v2`, and specialist tools (`erd_designer_v2`, `location_selector_v2`, `generation_behaviors_guide_v2`).
- Three major interactive components still had no native v2 route:
  - schema authoring editor (`schema_project`)
  - strategy workbench (`performance_workbench`)
  - multiprocess orchestrator (`execution_orchestrator`)
- Constraints required additive rollout, no runtime/data-semantics changes, and rollback-safe compatibility with existing classic routes.

## Decision
- Added new route constants in `src/gui_route_policy.py`:
  - `SCHEMA_V2_ROUTE = "schema_project_v2"`
  - `PERFORMANCE_V2_ROUTE = "performance_workbench_v2"`
  - `ORCHESTRATOR_V2_ROUTE = "execution_orchestrator_v2"`
- Added native v2 routes and screen classes:
  - `src/gui_v2_schema_project.py` -> `SchemaProjectV2Screen`
  - `src/gui_v2_performance_workbench.py` -> `PerformanceWorkbenchV2Screen`
  - `src/gui_v2_execution_orchestrator.py` -> `ExecutionOrchestratorV2Screen`
- Registered all new routes in `App` (`src/gui_home.py`) without removing classic routes.
- Updated v2 navigation:
  - `home_v2` now includes cards for all three new routes.
  - `schema_studio_v2` schema section actions now route to `schema_project_v2`.
  - dirty-state linking in `schema_studio_v2` now prefers `schema_project_v2` with fallback to classic `schema_project`.
  - `run_center_v2` header now includes navigation links to new dedicated run v2 routes.
- Added/extended tests for route registration, parity scenarios, and convergence contracts.

## Consequences
- The app now has native v2 route parity for all major interactive GUI components while preserving additive rollback safety.
- Classic routes remain available and unchanged for compatibility.
- `run_center_v2` remains a consolidated hub while dedicated run v2 routes coexist.
- Schema-studio v2 handoff now aligns with native v2 schema authoring.

## Rollback Notes
- Rollback can be performed by removing new v2 route registrations and restoring `schema_studio_v2` handoff to classic `schema_project`.
- No runtime/data semantics were changed; rollback is UI-route scoped.
- Classic routes remain intact, so immediate operational fallback is already available.
