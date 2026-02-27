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
- Priority P6 accessibility and keyboard flow pass (route-scoped shortcut lifecycle, focus traversal anchors, and dense table keyboard ergonomics on core interactive routes + legacy parity) (completed 2026-02-16)
- Priority P7 large-data responsiveness pass (chunked non-blocking table rendering and auto-paged heavy run-result grids on core interactive routes + legacy parity) (completed 2026-02-16)
- Priority P8 GUI regression/usability hardening (expanded v2 route/state-transition/cancel-fallback coverage and scenario-based acceptance checks) (completed 2026-02-16)
- Priority P9 native v2 route parity for missing GUI components (`schema_project_v2`, `performance_workbench_v2`, `execution_orchestrator_v2` with additive rollout and classic-route compatibility) (completed 2026-02-16)
- Priority P10 lazy route instantiation + idle prefetch (app shell now lazily creates v2 routes on first access, includes bounded likely-route idle prefetch, and adds startup timing harness coverage) (completed 2026-02-22)
- Priority P11 async project load/save UX hardening (schema v2 route now runs JSON load/save through non-blocking lifecycle jobs with busy/status feedback, duplicate-operation guards, and safe cancel/abort handling) (completed 2026-02-22)
- Priority P12 incremental validation engine (schema v2 route now performs debounced scope-aware validation updates for table/column/FK deltas while preserving full-project validation before generate/export actions) (completed 2026-02-22)
- Priority P13 scalable search/filter pipeline (schema v2 route now uses indexed + paged search rendering for columns and relationships instead of full detach/reattach filtering, reducing keystroke latency on large schemas) (completed 2026-02-22)
- Priority P14 undo/redo for schema authoring (schema v2 route now provides bounded command-stack undo/redo with keyboard shortcuts across table/column/FK/SCD edits) (completed 2026-02-22)
- Priority P15 persisted workspace state (schema v2 route now restores/saves per-route UI state including panel collapse, selected tab, preview page size, and preview visible-column order across app restarts) (completed 2026-02-22)
- Priority P16 command palette + quick navigation (global `Ctrl/Cmd+K` launcher now provides route jumps and active-screen high-frequency actions including validate/load/save/generate/plan/benchmark) (completed 2026-02-22)
- Priority P17 notification center and reduced modal friction (interactive routes now expose non-blocking notifications with history, success/info flows no longer use blocking info dialogs, and modal dialogs are reserved for blocking decisions/errors) (completed 2026-02-22)
- Priority P18 v2 visual system pass (shared visual tokens now define v2 typography/spacing/color roles/focus/button hierarchy and are applied consistently across the v2 route family) (completed 2026-02-22)
- Priority P19 guided empty states and first-run assistance (schema authoring and run-workflow routes now expose contextual empty states, inline next-action hints, and starter schema shortcuts to reduce time-to-first-success) (completed 2026-02-22)
- Specialist v2 route restoration (`erd_designer_v2`, `location_selector_v2`): restored reliable access via scrollable `home_v2` cards and reimplemented explicit open-classic tool actions in v2 specialist headers (completed 2026-02-16)
- Experimental schema demo route (`schema_demo_v2`): added strict mockup-style v2 schema screen based on `demopage.png` with full model-backed authoring/generation/save/export behaviors, constraints-tab advanced controls, and preloaded demo state (completed 2026-02-17)
- v2-only generator GUI migration (`schema_project_v2`): added structured inline generator configuration for all registered generators with raw JSON fallback, passthrough unknown-key preservation, source-column dependency auto-add behavior, advanced optional params controls (`null_rate`, `outlier_rate`, `outlier_scale`, bytes length), and dedicated v2 regression coverage (completed 2026-02-17)
- DG01 - Correlated column groups (joint realism): added first-class table-level correlation groups for multi-column numeric/categorical rank-correlation control with deterministic seeded sampling and GUI authoring exposure (completed 2026-02-22)
- DG02 - Lifecycle/state-transition generator: implemented `state_transition` with allowed transition maps, explicit terminal states, dwell-time controls, deterministic per-entity trajectories, and SCD2 tracked-column transition-step mutation support (completed 2026-02-23)
- DG03 - Cross-table temporal integrity planner: implemented project-level `timeline_constraints` with deterministic FK-linked temporal interval enforcement (preserve-valid / clamp-invalid / repair-null-or-unparseable), canonical validation/runtime errors, GUI project-level authoring exposure, and regression coverage (completed 2026-02-23)
- DG04 - Safe derived-expression engine: implemented `derived_expr` constrained expression DSL (no `eval`) with deterministic same-row evaluation, explicit `depends_on` source declaration, strict fail-fast runtime policy, GUI dependency auto-assist, and regression coverage (completed 2026-02-24)
- DG05 - Attribute-aware FK selection: implemented optional `ForeignKeySpec.parent_selection` weighted parent cohort profiles (`parent_attribute`, `weights`, `default_weight`) for deterministic FK skew modeling while preserving min/max child cardinality constraints (completed 2026-02-24)
- DG06 - Missingness and data-quality profile modeling: implemented optional project-level `data_quality_profiles` for deterministic MCAR/MAR/MNAR-style missingness and controlled quality issues (`format_error`, `stale_value`, `drift`) with actionable validation/runtime errors and GUI project-level authoring support (completed 2026-02-24)
- DG07 - Sample-driven profile fitting: implemented optional project-level `sample_profile_fits` with CSV-driven profile inference (`sample_source`) and deterministic frozen profile overrides (`fixed_profile`) for target columns, plus actionable validation/runtime errors and GUI project-level authoring support (completed 2026-02-24)
- DG08 - Child-cardinality distribution modeling: implemented optional FK-level `child_count_distribution` profiles (`uniform`, `poisson`, `zipf`) for deterministic distribution-shaped child counts while preserving FK min/max integrity and GUI relationship authoring support (completed 2026-02-25)
- DG09 - Locale-coherent identity bundles: implemented optional project-level `locale_identity_bundles` locale-pack contracts for deterministic coherent names/addresses/phones/postcodes/currency fields with related-table FK projections and validation/GUI/test coverage (completed 2026-02-26)
- DG10 - Streaming generation for very large schemas: implemented memory-bounded streaming generation/export flow via `generate_project_rows_streaming` and strategy runtime integration for deterministic ordering and FK-safe CSV/SQLite outputs (completed 2026-02-26)
- Schema design modes for `schema_project_v2`: implemented one-route in-page `simple|medium|complex` UI modes with header selector, mode-scoped control visibility, mode-scoped generator allowlists, structured-form progressive disclosure, persisted workspace mode state, and non-destructive downgrade behavior that preserves hidden advanced values (completed 2026-02-26)

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
No active data-generation feature candidates are currently queued.

## Data Generation Backlog (Prioritized)

### Summary
- Structural realism baseline now includes DG10 streaming generation and DG09 locale-coherent identity bundles.
- No active data-generation feature candidates are currently queued.

### Prioritized Next Steps
No active data-generation priorities are currently queued.

### Test Cases and Scenarios
- Determinism regression: same schema + seed must reproduce identical outputs for DG08-DG10 while preserving DG01-DG07 determinism guarantees.
- Correlation fidelity regression tests: generated column pairs/groups must continue meeting configured DG01 rank-correlation targets within defined tolerance bands.
- Transition validity regression tests: DG02 continues to forbid invalid/self transitions and respect dwell-time constraints.
- Temporal integrity tests: DG03 enforces cross-table event ordering for FK-linked rows without violating existing date/datetime constraints.
- Expression safety tests: DG04 parser/evaluator rejects unsafe syntax and emits actionable location + fix hints.
- FK realism tests: DG05 parent selection frequencies follow configured cohort/attribute weights.
- Missingness-quality tests: DG06 null/error/drift rates match configured profiles by table/column segments.
- Profile-fit reproducibility tests: DG07 inferred profiles are stable for same sample inputs and deterministic when reused.
- DG08 regression tests: child-count distributions remain deterministic and continue approximating configured shapes while preserving FK integrity.
- Locale coherence tests: DG09 field bundles remain internally consistent (country/postcode/phone/currency/date formatting).
- Large-scale performance tests: DG10 maintains bounded memory and deterministic row ordering under large row counts and multi-table exports.

### Assumptions and Defaults
- Use `DGxx` identifiers to avoid collision with existing GUI-priority `Pxx` series.
- All DG features are additive; existing schemas remain valid unless opt-in DG fields are used.
- No external dependencies are introduced; implementations remain pure Python stdlib.
- Backward-compatible JSON policy: new fields default safely when absent.
- Actionable error contract remains mandatory: `<Location>: <issue>. Fix: <hint>.`
- GUI authoring exposure is required for each DG feature before feature completion status can be marked.

## GUI Refinement Backlog (Prioritized)

### Summary
- Prioritize measurable speed wins first (startup, filtering, validation, load/save responsiveness).
- Follow with workflow reliability and productivity (preserve P14 undo/redo, P15 workspace-state continuity, P16 command-palette productivity, P17 notification-center behavior, and P18 visual-token consistency).
- Finish with UX/look-and-feel cohesion (onboarding/empty states).

### Prioritized Next Steps
No active GUI refinement priorities are currently queued.

### Test Cases and Scenarios
- Startup performance regression tests: preserve P10 cold-start and startup-memory gains while delivering subsequent priorities.
- Large-schema responsiveness tests: preserve P11 non-blocking project load/save UX, P12 incremental validation responsiveness, P13 indexed/paged search/filter responsiveness, and P14 undo/redo responsiveness while scaling subsequent priorities.
- Authoring resilience tests: preserve P14 undo/redo correctness across add/edit/remove/move operations and SCD/BK edits.
- Session continuity tests: preserve P15 restored panel/tab/preview/column-chooser state across app restart and route switches.
- Keyboard productivity regression tests: preserve command palette discoverability, action execution, and shortcut coexistence with existing route-scoped bindings (P16).
- Dialog/notification behavior regression tests: preserve non-modal informational/success flows and keep blocking confirmations modal/actionable (P17).
- Visual consistency regression checks: preserve tokenized spacing/typography/color/focus/button hierarchy across all native v2 routes (P18).
- Onboarding usability scenarios: preserve first-run guided empty states and starter-schema shortcuts so users can load/create schema and generate preview without external documentation.

### Assumptions and Defaults
- Keep additive rollout with rollback safety; no removal of classic/fallback routes in this cycle.
- No external dependencies; Python stdlib + Tkinter only.
- Deterministic generation and JSON compatibility remain non-negotiable.
- Performance acceptance defaults:
  - preserve P10 startup improvements and prevent regressions to eager all-route initialization,
  - preserve P13 large-list filter response target <= 100 ms for typical keystrokes,
  - preserve P14 bounded undo/redo history behavior and shortcut-driven authoring recovery on schema v2,
  - preserve P15 workspace-state restore continuity for panel/tab/preview preferences across restarts,
  - preserve P16 global command-palette launch and route/action dispatch behavior without regressing route-scoped shortcuts,
  - preserve P17 non-blocking notification-history flows and avoid reintroducing modal info/success dialogs,
  - preserve P18 shared v2 visual tokens as the single source for route-family color/type/spacing/focus/button hierarchy decisions,
  - preserve P11 non-blocking project load/save behavior and P12 debounced incremental validation behavior without main-thread freezes during post-load/post-edit validation updates.
- Prioritize by user-visible impact and implementation risk: speed first, then workflow efficiency, then visual/UX polish.

## Deferred
- None.
