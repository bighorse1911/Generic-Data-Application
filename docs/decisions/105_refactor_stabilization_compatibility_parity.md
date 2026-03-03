# Decision 105: Refactor Stabilization and Compatibility Parity

## Context
After the domain-first structural refactor, targeted GUI regressions remained:
- legacy patch points in `src.gui_v2_redesign` were no longer module-visible,
- schema-v2 starter fixture shortcut resolved the fixture path relative to `src/gui`,
- one visual-system test asserted a pre-refactor header container shape,
- GUI suite execution was sensitive to Tk lifecycle bleed in one-process discovery runs.

## Decision
Stabilize before deeper decomposition by:
- restoring legacy `src.gui_v2_redesign` module-level helper exports,
- fixing starter fixture resolution to repo-root-relative `tests/fixtures/default_schema_project.json`,
- aligning visual token test assertions to canonical `_header_host` architecture,
- adding `run_gui_tests_isolated.py` and documenting it as preferred GUI-suite execution guidance.

## Consequences
- Backward compatibility shims remain reliable for existing tests and patch points.
- First-run starter fixture shortcut behavior is restored.
- GUI visual-system assertions now reflect current architecture contracts.
- GUI regression runs become more deterministic without altering non-GUI test discovery behavior.
