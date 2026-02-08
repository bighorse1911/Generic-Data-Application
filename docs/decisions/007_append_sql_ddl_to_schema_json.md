# Context
- Prompt requested appending a SQL DDL string to saved schema project JSON, covering all tables and FK relationships, using the default SQL dialect (not SQLite-specific DDL).
- Prompt also required updating `tests/fixtures/default_schema_project.json` accordingly.

# Decision
- Added DDL generation in `src/schema_project_io.py` and appended it as `sql_ddl` during `save_project_to_json()`.
- DDL now includes:
  - `CREATE TABLE` statements for each table.
  - Column type mapping to default SQL types (`INTEGER`, `DOUBLE PRECISION`, `TEXT`, `BOOLEAN`, `DATE`, `TIMESTAMP`).
  - `NOT NULL`, `PRIMARY KEY`, and `UNIQUE` constraints where defined.
  - `FOREIGN KEY` constraints for defined relationships.
- `load_project_from_json()` remains backward compatible and now validates that optional `sql_ddl` is a string when present, with a fix-hint error.
- Updated `tests/fixtures/default_schema_project.json` to include the new trailing `sql_ddl` field.

# Consequences
- JSON exports from GUI/save path now carry machine-readable schema DDL without changing generation behavior.
- Existing/legacy JSON files continue to load.
- Added tests to prevent regressions around DDL append behavior and invalid `sql_ddl` config type.
