# Context
- User requested implementation start for deferred feature `Performance scaling` with small, safe edits, GUI accessibility, actionable validation errors, and green tests.
- Existing plan in `NEXT_DECISIONS.md` defined phase sequencing where phase 1 introduces UI + profile validation + estimate diagnostics before chunk runtime integration.

# Decision
- Implemented phase-1 performance scaling slice:
  - Added `performance_workbench` route and screen in `src/gui_home.py`.
  - Added new backend module `src/performance_scaling.py` with:
    - `PerformanceProfile` construction/validation,
    - FK-aware row-override guardrails,
    - deterministic workload estimate and summary helpers.
  - Added tests in `tests/test_performance_scaling.py` and updated GUI navigation invariants in `tests/test_invariants.py`.
  - Updated canon docs (`PROJECT_CANON.md`, `NEXT_DECISIONS.md`, `DATA_SEMANTICS.md`, `GUI_WIREFRAME_SCHEMA.md`) to record behavior and status.

# Consequences
- Users can now access a dedicated GUI page to configure a performance profile and estimate workload safely before generation.
- Validation errors use canonical actionable format and reject invalid profile values early.
- This is a non-breaking phase-1 foundation; chunk planning/runtime integration remains for later phases.
