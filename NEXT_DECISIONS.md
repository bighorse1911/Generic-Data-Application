## Active Direction
Direction 1 - Smarter Data

## Completed Features (simple list)
- Deferred Feature A - Performance scaling (completed 2026-02-14)
- Deferred Feature B - Multiprocessing (completed 2026-02-14)
- Deferred Feature C - Full visual redesign (completed 2026-02-14)
- ERD designer (completed 2026-02-14)
- Location selector (completed 2026-02-14)
- Generation behaviors guide page (completed 2026-02-12)
- Priority 1 rollout phases 1-5 (`if_then`, `time_offset`, `hierarchical_category`, validation heatmap enhancements, SCD2 child-table support) (completed 2026-02-14)
- CSV sampling enhancements (`sample_csv`, dependent `match_column` support, repo-relative path portability) (completed 2026-02-14)
- Direction 3 decimal migration and float compatibility (`float` -> `decimal` canonical authoring) (completed 2026-02-14)
- Extensible `bytes` dtype (completed 2026-02-14)
- Realistic distributions (`uniform_int`, `uniform_float`, `normal`, `lognormal`, `choice_weighted`) (completed 2026-02-14)
- Ordered choices generator (`ordered_choice`) (completed 2026-02-14)
- GUI kit modernization phases A/B/C (completed 2026-02-14)
- Business-key behavior controls and `business_key_unique_count` support (completed 2026-02-14)
- Canonical spec adoption (`DATA_SEMANTICS.md`, `GUI_WIREFRAME_SCHEMA.md`) (completed 2026-02-14)

## Completed Directions
- Direction 2 - Modular GUI Adoption (incremental, low-risk)
- Direction 3 - Refactor float -> decimal; move semantic numeric types into generators
- Direction 4 - Performance scaling (deferred feature A)
- Direction 5 - Multiprocessing (deferred feature B)
- Direction 6 - Full visual redesign

## In Progress
- None.

## Next Candidates
**Priority 1 (future features):**
- [P1] Native v2 tool parity: migrate `erd_designer_v2`, `location_selector_v2`, and `generation_behaviors_guide_v2` from bridge screens to native v2 implementations.
- [P2] Run workflow convergence: align `run_center_v2`, `performance_workbench`, and `execution_orchestrator` around shared config/progress/failure/history UX patterns.
- [P3] Schema route consolidation: prepare phased retirement criteria for `schema_project_legacy` after parity validation and rollback checks.
- [P4] Async lifecycle consistency: standardize start/cancel/retry/fallback state handling and reduce Tk callback teardown noise.
- [P5] Validation/error UX consistency: enforce canonical actionable error format and consistent inline/status/dialog surfaces across all screens.
- [P6] Accessibility and keyboard flow: improve focus order, traversal, shortcut discoverability, and dense table interaction ergonomics.
- [P7] Large-data responsiveness: improve paged/virtualized table rendering and non-blocking refresh behavior in heavy views.
- [P8] GUI regression/usability hardening: expand v2 route/state-transition/cancel-fallback coverage and scenario-based acceptance checks.

## GUI Refinement Backlog (Prioritized)

### Summary
- Focus refinements on reducing route fragmentation, improving run-workflow consistency, and hardening UX quality.
- Keep momentum after Feature C completion with clear execution order and explicit acceptance coverage.

### Prioritized Next Steps
- **P1:** Replace v2 bridge pages with native v2 tool pages while preserving behavior contracts.
- **P2:** Converge run workflows into shared UI/runtime patterns across `run_center_v2`, `performance_workbench`, and `execution_orchestrator`.
- **P3:** Consolidate schema authoring routes with a deprecation path for `schema_project_legacy` once parity gates pass.
- **P4:** Standardize async job lifecycle UX and centralize run lifecycle behavior.
- **P5:** Strengthen validation and error surfacing consistency across all screens.
- **P6:** Execute accessibility and keyboard-flow pass for power-user navigation.
- **P7:** Improve large-data UI responsiveness with virtualized/paged grids and non-blocking refresh paths.
- **P8:** Expand regression/usability hardening for v2 route contracts and state transitions.

### Planned Public API / Interface / Type Additions
- `src/gui_kit/run_lifecycle.py`: shared run state helpers for start/cancel/progress/fallback semantics.
- `src/gui_kit/error_surface.py`: unified error presentation adapter for modal/status/inline consistency.
- `src/gui_kit/table_virtual.py`: shared virtualized/paged table adapter for large result sets.
- `src/gui_v2/viewmodels.py`: extend v2 viewmodels for native ERD/location/guide states.
- `src/gui_v2/commands.py`: add command handlers for native v2 ERD/location/guide actions.

### Test Cases and Scenarios
- Route contract tests: all v2 routes load, navigate, and expose required controls.
- Run lifecycle tests: start/cancel/retry/fallback transitions are deterministic and UI-safe.
- Error contract tests: representative failures on each major screen match canonical actionable format.
- Dirty-navigation tests: guarded transitions from schema flows are enforced correctly.
- Large-data UX tests: paged/virtualized views remain responsive and preserve row/column selection behavior.
- Regression parity tests: native v2 tool pages preserve behavior currently provided by bridge-target routes.

### Assumptions and Defaults
- Keep additive rollout and preserve current production routes until parity tests pass.
- No external dependencies; Python stdlib + Tkinter only.
- Deterministic generation and JSON compatibility remain non-negotiable.
- Prioritization defaults to delivery value plus risk reduction (P1 through P8).

## Deferred
- None.
