# Context
- Task request: add ERD-page schema export so authored schemas can be loaded in schema designer, and add table/column edit capabilities on ERD page.
- Existing ERD page already supported in-page create/add authoring but lacked direct edit actions and JSON export.

# Decision
- Added ERD helper APIs in `src/erd_designer.py`:
  - `update_table_in_erd_project(...)`
  - `update_column_in_erd_project(...)`
  - `export_schema_project_to_json(...)`
- Added ERD GUI controls in `src/gui_home.py`:
  - `Export schema JSON...` action in input/export controls.
  - table edit row (select table, rename, row-count update).
  - column edit row (select table/column, edit name/dtype/PK/nullability).
- Kept actionable validation messages in canonical form: `ERD Designer / <Location>: <issue>. Fix: <hint>.`
- Added regression tests for helper logic and GUI flow updates.

# Consequences
- ERD-authored schemas can now be exported to `.json` and loaded directly into schema designer routes.
- Users can edit existing table/column definitions without leaving `erd_designer`.
- FK references are updated when table/column names are edited, reducing accidental breakage.
