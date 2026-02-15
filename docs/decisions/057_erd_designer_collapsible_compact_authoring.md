# Context
- Task request: reduce ERD authoring UI footprint by adding a collapse option and sharing add/edit controls for tables and columns.
- Existing ERD authoring UI had separate rows for add/edit table and add/edit column, which consumed vertical space.

# Decision
- Added a collapse/expand toggle for the ERD schema authoring panel in `src/gui_home.py`.
- Replaced separate add/edit table rows with one shared table editor:
  - blank table selection = add new table,
  - selected table = edit existing table.
- Replaced separate add/edit column rows with one shared column editor:
  - blank column selection = add new column,
  - selected column = edit existing column.
- Kept legacy helper methods (`_add_table`, `_edit_table`, `_add_column`, `_edit_column`) intact for compatibility and regression safety.
- Added GUI integration assertions in `tests/test_invariants.py` for collapse toggle and shared save flows.

# Consequences
- ERD authoring takes less space and is easier to use during canvas-focused workflows.
- Users can quickly switch between add and edit modes without changing panels.
- Existing tests and method entry points remain compatible.
