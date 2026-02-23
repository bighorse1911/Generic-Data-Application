# 088 - P19 Guided Empty States and First-Run Assistance

## Context
- Priority P19 in `NEXT_DECISIONS.md` targeted first-run friction and unclear next steps in GUI authoring/run workflows.
- `schema_project_v2` started with an empty project but lacked guided starter actions.
- Shared run-workflow routes (`run_center_v2`, `performance_workbench*`, `execution_orchestrator*`) had empty result tabs without explicit next-action guidance.

## Decision
- Add first-run quick-start controls to the shared schema editor base (`src/gui_schema_editor_base.py`):
  - `Create starter schema` shortcut (built-in deterministic starter project with PK + FK shape),
  - `Load starter fixture` shortcut (`tests/fixtures/default_schema_project.json`),
  - `Open Generate tab` shortcut.
- Add contextual empty-state hint strings in schema authoring regions:
  - project-level onboarding hint,
  - tables empty-state hint,
  - relationships empty-state hint,
  - generate/preview empty-state hint.
- Keep hints state-aware by refreshing on key lifecycle transitions:
  - table/FK refresh,
  - generate/clear preview,
  - load project,
  - run/busy state changes.
- Clear generated-preview state on project load in the kit schema route to prevent stale preview context after switching schemas.
- Extend shared run-workflow surface (`src/gui_tools/run_workflow_view.py`) with:
  - inline `next_action_var` guidance under run config,
  - per-results-tab empty-state overlays,
  - dynamic guidance updates from schema path changes and result-table row updates.

## Consequences
- First-run users can create or load a starter schema and reach generated preview without external docs.
- Run-workflow routes now communicate clear next steps before any diagnostics/plan/worker/history data exists.
- Guidance behavior is centralized in shared primitives, so v2/classic run-route parity remains intact.
- Added regression coverage:
  - `tests/test_gui_p19_onboarding_empty_states.py`,
  - updated `tests/test_gui_run_workflow_convergence.py` with first-run guidance assertions.
