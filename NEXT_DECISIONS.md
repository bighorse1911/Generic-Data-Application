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
- Priority P1 native v2 specialist tool parity (`erd_designer_v2`, `location_selector_v2`, `generation_behaviors_guide_v2` with hidden `*_v2_bridge` rollback routes) (completed 2026-02-15)
- Priority P2 run workflow convergence (`run_center_v2`, `performance_workbench`, and `execution_orchestrator` now share lifecycle/runtime/error/table workflow primitives and section model) (completed 2026-02-15)
- Priority P3 schema route consolidation (`schema_project` is the only primary authoring route; hidden fallback routes `schema_project_kit` alias and deprecated `schema_project_legacy` retained for one release cycle) (completed 2026-02-15)
- Priority P4 async lifecycle consistency (shared teardown-safe UI dispatch, centralized run lifecycle terminal transitions, schema-kit shared job lifecycle, and legacy callback teardown guards) (completed 2026-02-15)
- Priority P5 validation/error surface consistency (interactive routes now use shared actionable error/warning surfaces with route-standardized dialog titles; read-only routes remain explicitly excluded) (completed 2026-02-15)

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
- [P6] Accessibility and keyboard flow: improve focus order, traversal, shortcut discoverability, and dense table interaction ergonomics.
- [P7] Large-data responsiveness: improve paged/virtualized table rendering and non-blocking refresh behavior in heavy views.
- [P8] GUI regression/usability hardening: expand v2 route/state-transition/cancel-fallback coverage and scenario-based acceptance checks.

## GUI Refinement Backlog (Prioritized)

### Summary
- Focus refinements on reducing route fragmentation, improving run-workflow consistency, and hardening UX quality.
- Keep momentum after Feature C completion with clear execution order and explicit acceptance coverage.

### Prioritized Next Steps
- **P6:** Execute accessibility and keyboard-flow pass for power-user navigation.
- **P7:** Improve large-data UI responsiveness with virtualized/paged grids and non-blocking refresh paths.
- **P8:** Expand regression/usability hardening for v2 route contracts and state transitions.

### Test Cases and Scenarios
- Route contract tests: all v2 routes load, navigate, and expose required controls.
- Run lifecycle tests: start/cancel/retry/fallback transitions are deterministic and UI-safe.
- Error contract tests: representative failures on each major screen match canonical actionable format.
- Dirty-navigation tests: guarded transitions from schema flows are enforced correctly.
- Large-data UX tests: paged/virtualized views remain responsive and preserve row/column selection behavior.
- Regression parity tests: native v2 tool pages preserve behavior currently provided by bridge-target routes.

### Assumptions and Defaults
- Keep additive rollout and preserve current production routes until parity tests pass.
- P1 completion default: keep hidden `*_v2_bridge` rollback routes for one release cycle before removal consideration.
- No external dependencies; Python stdlib + Tkinter only.
- Deterministic generation and JSON compatibility remain non-negotiable.
- Prioritization defaults to delivery value plus risk reduction (P6 through P8 in current backlog).

## Deferred
- None.
