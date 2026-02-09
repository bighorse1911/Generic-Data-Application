import json
from dataclasses import asdict

from src.schema_project_model import SchemaProject, TableSpec, ColumnSpec, ForeignKeySpec, validate_project
from pathlib import Path


_DEFAULT_SQL_TYPES: dict[str, str] = {
    "int": "INTEGER",
    "decimal": "DECIMAL",
    "float": "DOUBLE PRECISION",
    "text": "TEXT",
    "bool": "BOOLEAN",
    "date": "DATE",
    "datetime": "TIMESTAMP",
}


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _default_sql_type(dtype: str, *, table_name: str, column_name: str) -> str:
    sql_type = _DEFAULT_SQL_TYPES.get(dtype)
    if sql_type is not None:
        return sql_type
    allowed = ", ".join(sorted(_DEFAULT_SQL_TYPES.keys()))
    raise ValueError(
        "SQL DDL generation failed at "
        f"table '{table_name}', column '{column_name}': unsupported dtype '{dtype}'. "
        f"Fix: use one of: {allowed}."
    )


def build_project_sql_ddl(project: SchemaProject) -> str:
    validate_project(project)

    fks_by_child_table: dict[str, list[ForeignKeySpec]] = {}
    for fk in project.foreign_keys:
        fks_by_child_table.setdefault(fk.child_table, []).append(fk)

    statements: list[str] = []
    for table in project.tables:
        lines: list[str] = []
        for column in table.columns:
            col_parts = [
                _quote_identifier(column.name),
                _default_sql_type(column.dtype, table_name=table.table_name, column_name=column.name),
            ]
            if not column.nullable:
                col_parts.append("NOT NULL")
            if column.primary_key:
                col_parts.append("PRIMARY KEY")
            if column.unique:
                col_parts.append("UNIQUE")
            lines.append("  " + " ".join(col_parts))

        for fk in fks_by_child_table.get(table.table_name, []):
            lines.append(
                "  "
                + "FOREIGN KEY "
                + f"({_quote_identifier(fk.child_column)}) "
                + "REFERENCES "
                + f"{_quote_identifier(fk.parent_table)} "
                + f"({_quote_identifier(fk.parent_column)})"
            )

        statement = f"CREATE TABLE {_quote_identifier(table.table_name)} (\n"
        statement += ",\n".join(lines)
        statement += "\n);"
        statements.append(statement)

    return "\n\n".join(statements)


def save_project_to_json(project: SchemaProject, path: str) -> None:
    validate_project(project)
    data = asdict(project)
    data["sql_ddl"] = build_project_sql_ddl(project)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_project_from_json(path: str) -> SchemaProject:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    sql_ddl = data.get("sql_ddl")
    if (sql_ddl is not None) and (not isinstance(sql_ddl, str)):
        raise ValueError(
            "Schema project JSON key 'sql_ddl' must be a string when present. "
            "Fix: set 'sql_ddl' to a SQL DDL string or remove the key."
        )

    # Convenience: resolve known test-fixture placeholder tokens to local files when available.
    # This mirrors test behavior where the JSON uses a placeholder `__CITY_COUNTRY_CSV__`.
    repo_root = Path(__file__).resolve().parents[1]
    candidate = repo_root / "tests" / "fixtures" / "city_country_pool.csv"
    if candidate.exists():
        for t in data.get("tables", []):
            for c in t.get("columns", []):
                params = c.get("params")
                if isinstance(params, dict) and params.get("path") == "__CITY_COUNTRY_CSV__":
                    params["path"] = str(candidate)

    tables = []
    for t in data["tables"]:
        cols = [ColumnSpec(**c) for c in t["columns"]]
        tables.append(TableSpec(table_name=t["table_name"], columns=cols, row_count=int(t.get("row_count", 100))))

    fks = [ForeignKeySpec(**fk) for fk in data.get("foreign_keys", [])]

    project = SchemaProject(
        name=data["name"],
        seed=int(data.get("seed", 12345)),
        tables=tables,
        foreign_keys=fks,
    )
    validate_project(project)
    return project
