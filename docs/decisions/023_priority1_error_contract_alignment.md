# Context
- Priority 1 in `NEXT_DECISIONS.md` required aligning validator/runtime/GUI error wording to the canonical contract from `DATA_SEMANTICS.md` section 8 and `GUI_WIREFRAME_SCHEMA.md` section 3.2.
- Several validation and runtime messages still lacked consistent `Location + issue + Fix` formatting across:
  - `validate_project()` in `src/schema_project_model.py`,
  - runtime generation failures in `src/generator_project.py` and `src/generators.py`,
  - GUI detailed validation and pre-submit checks in `src/gui_schema_project.py`.

# Decision
- Standardized remaining non-canonical validation/runtime/GUI errors to the canonical shape:
  - `<Location>: <issue>. Fix: <hint>.`
- Added small message-format helper functions in each relevant module to keep wording consistent:
  - `_validation_error(...)` in `src/schema_project_model.py`,
  - `_runtime_error(...)` in `src/generator_project.py`,
  - `_generator_error(...)` in `src/generators.py`,
  - `_gui_error(...)` in `src/gui_schema_project.py`.
- Updated focused tests in `tests/test_invariants.py` to assert canonical messaging across validator/runtime/GUI paths.

# Consequences
- Validation and runtime failures now present consistent, actionable messages across backend and GUI surfaces.
- Existing behavior for generation, FK integrity, GUI navigation, and JSON IO remains unchanged; only error wording and guardrail clarity were improved.
- Full test suite remains green after the change (`python -m unittest discover -s tests -p "test_*.py"`).
