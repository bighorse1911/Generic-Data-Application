# Context
- Prompt requested full implementation of Deferred Feature B (Multiprocessing) under standard-library/Tkinter constraints, with deterministic behavior, actionable errors, and full regression safety.
- Existing canon/roadmap docs already defined a target `execution_orchestrator` screen and backend multiprocess runtime responsibilities, but no implementation existed.

# Decision
- Implemented a new runtime module `src/multiprocessing_runtime.py` for:
  - multiprocess config parsing/validation,
  - deterministic FK-stage partition planning,
  - worker-event orchestration with retry/fallback/cancel handling,
  - run-ledger save/load/metadata validation.
- Implemented new GUI screen `ExecutionOrchestratorScreen` in `src/gui_execution_orchestrator.py` and wired route `execution_orchestrator` into `src/gui_home.py` (Home button + App route registration).
- Added tests in `tests/test_multiprocessing_runtime.py` and expanded GUI route contract checks in `tests/test_invariants.py`.
- Updated canon/roadmap docs (`PROJECT_CANON.md`, `NEXT_DECISIONS.md`, `DATA_SEMANTICS.md`, `GUI_WIREFRAME_SCHEMA.md`) to mark Feature B complete and remove it from deferred status.

# Consequences
- Multiprocessing feature is now accessible in GUI with deterministic, validated execution controls and failure/fallback visibility.
- Run configuration and run-ledger artifacts can be persisted and re-validated for safer recovery flows.
- Regression coverage now includes Feature B runtime and navigation contracts while preserving existing generation/FK/JSON IO behavior.
