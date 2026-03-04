# Context
- A concrete request asked for an experimental PyQt recreation of the schema project page while preserving all canonical Tkinter routes and behavior contracts.
- The workspace has strict regression tests around route inventory and no external dependency assumptions for default flows.

# Decision
- Added an isolated optional experiment package at `src/experimental/pyqt_schema_project` with:
  - debug gate `GDA_ENABLE_PYQT_EXPERIMENT=1`,
  - subprocess launcher API (`is_experiment_enabled`, `check_pyqt6_available`, `launch_pyqt_schema_project`),
  - PyQt entrypoint/window/models/json editor,
  - pure-Python controller wrapping canonical schema/generation/runtime modules.
- Added an env-gated `home_v2` card (`Schema Project PyQt Experiment`) that launches the isolated subprocess and does not add/modify canonical app route keys.
- Added regression tests for launcher gating/launch behavior, controller behavior, and home-v2 gate visibility.

# Consequences
- The experiment is accessible for developers when explicitly enabled and remains absent by default.
- Canonical Tk route inventory and existing regression contracts remain intact.
- Optional PyQt dependency is isolated; missing PyQt6 produces actionable launch errors instead of breaking core app/tests.
- The experiment can be removed with low risk by deleting `src/experimental/pyqt_schema_project` and the single `home_v2` launcher hook.
