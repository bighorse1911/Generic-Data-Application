# Context
- Prompt requested a new GUI page `ERD Designer` with MVP scope: take project schema input and output a high-quality entity relationship diagram, including options for relationships, column names, and datatypes.
- Constraints required standard library only, Tkinter GUI, actionable errors, and no regressions.

# Decision
- Added a new Home route `erd_designer` with `ERDDesignerScreen` in `src/gui_home.py`.
- Added `src/erd_designer.py` for reusable ERD logic:
  - schema loading with actionable validation errors,
  - deterministic table/relationship layout generation,
  - column line formatting with PK/FK markers and optional datatype display.
- Implemented ERD controls and rendering:
  - schema JSON path input + browse + render action,
  - toggles for relationships, column names, datatypes,
  - scrollable canvas rendering of table nodes and FK edges.
- Added tests:
  - `tests/test_erd_designer.py` for load/layout/format/error helpers,
  - updated `tests/test_invariants.py` GUI navigation contract for `erd_designer`.
- Updated canonical docs and roadmap status files.

# Consequences
- Users can now visually inspect schema structure and FK connectivity directly in-app before/after generation workflows.
- The MVP remains additive and non-invasive: no changes to generation semantics, JSON schema format, or FK runtime behavior.
- Regression suite remains green, including GUI navigation contract checks.
