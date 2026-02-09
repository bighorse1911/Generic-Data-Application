# Context
- Prompt requested commenting/restructuring/documentation updates for the GUI kit.
- Requirement emphasized machine readability so the GUI kit can be reused consistently.
- Changes needed to remain low-risk and preserve existing generation, FK integrity, GUI flow, and JSON IO behavior.

# Decision
- Added a machine-readable component catalog in `src/gui_kit/__init__.py`:
  - `GUIKitComponent` (`TypedDict`) for catalog schema.
  - `_COMPONENT_CATALOG` with stable entries for each public GUI kit export.
  - `get_component_catalog()` as the public read API.
  - `_validate_component_catalog()` import-time validation with actionable error messages.
- Added module-level `__all__` exports and concise method/function docstrings in:
  - `src/gui_kit/forms.py`
  - `src/gui_kit/layout.py`
  - `src/gui_kit/panels.py`
  - `src/gui_kit/scroll.py`
  - `src/gui_kit/table.py`
- Added `tests/test_gui_kit_catalog.py` to enforce catalog shape, export visibility, and module importability.

# Consequences
- GUI kit metadata is now both human-readable (docstrings) and machine-readable (typed catalog).
- Future screens/tools can reliably introspect kit components without scanning source heuristically.
- Behavior of generation logic, FK integrity handling, schema JSON IO, and existing GUI navigation remains unchanged.
