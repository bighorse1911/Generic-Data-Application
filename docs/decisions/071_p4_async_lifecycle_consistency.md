# Context
- Priority P4 in `NEXT_DECISIONS.md` required standardizing async lifecycle UX and centralizing run lifecycle behavior.
- Run routes already shared run-workflow surfaces, but lifecycle terminal transitions and callback dispatch safety still had route-level variation.
- Schema-kit long jobs and legacy schema worker callbacks needed a consistent teardown-safe dispatch posture to reduce Tk teardown noise.

# Decision
- Added shared teardown-safe UI dispatch module `src/gui_kit/ui_dispatch.py`:
  - `safe_dispatch(...)`
  - `UIDispatcher`
- Added shared non-run async lifecycle module `src/gui_kit/job_lifecycle.py`:
  - `JobLifecycleState`
  - `JobLifecycleController`
- Extended `src/gui_kit/run_lifecycle.py`:
  - explicit terminal transition helpers (`transition_complete`, `transition_failed`, `transition_cancelled`)
  - optional fallback/retry-aware internal state tracking fields
  - teardown-safe terminal callback dispatch integration in `run_async(...)` via `UIDispatcher`
- Updated `src/gui_kit/layout.py` `BaseScreen.safe_threaded_job(...)` to use teardown-safe dispatch polling.
- Updated run screens to consistently use centralized lifecycle and safe event marshalling:
  - `src/gui_home.py` (`PerformanceWorkbenchScreen`)
  - `src/gui_execution_orchestrator.py`
  - `src/gui_v2_redesign.py` (`RunCenterV2Screen`)
- Updated schema-kit long jobs (`src/gui_schema_project_kit.py`) to use `JobLifecycleController` while preserving existing status/phase wording and non-cancelable behavior.
- Updated legacy schema fallback (`src/gui_schema_project.py`) with blocker-level teardown-safe callback scheduling guard for background worker callbacks.
- Added/updated tests:
  - `tests/test_gui_kit_ui_dispatch.py`
  - `tests/test_gui_kit_job_lifecycle.py`
  - `tests/test_gui_kit_run_lifecycle.py`
  - `tests/test_gui_async_lifecycle_consistency.py`
  - `tests/test_gui_run_workflow_convergence.py` (lifecycle/dispatcher presence checks)

# Consequences
- Async lifecycle behavior is now more uniform across run routes and schema-kit long jobs without changing route keys or required widget contracts.
- Tk teardown callback noise is reduced by safe callback dispatch behavior (callbacks are dropped when UI hosts are no longer alive).
- Existing user-visible status/phase copy remains stable; retry/fallback behavior remains implicit and unchanged in UI controls.
- Legacy schema route remains deprecated and hidden, with only blocker-level safety hardening in this slice.
