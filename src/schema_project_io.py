import json
from dataclasses import asdict

from src.schema_project_model import SchemaProject, TableSpec, ColumnSpec, ForeignKeySpec, validate_project
from src.project_paths import to_repo_relative_path


_DEFAULT_SQL_TYPES: dict[str, str] = {
    "int": "INTEGER",
    "decimal": "DECIMAL",
    "float": "DOUBLE PRECISION",
    "text": "TEXT",
    "bool": "BOOLEAN",
    "date": "DATE",
    "datetime": "TIMESTAMP",
    "bytes": "BLOB",
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
    _normalize_sample_csv_paths(data)
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

    _normalize_sample_csv_paths(data)

    tables = []
    for t in data["tables"]:
        raw_business_key_unique_count = t.get("business_key_unique_count")
        business_key_unique_count = None
        if raw_business_key_unique_count is not None:
            if isinstance(raw_business_key_unique_count, bool):
                raise ValueError(
                    f"Table '{t.get('table_name', '<unknown>')}': business_key_unique_count must be an integer when provided. "
                    "Fix: set business_key_unique_count to a positive whole number or omit it."
                )
            try:
                business_key_unique_count = int(raw_business_key_unique_count)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Table '{t.get('table_name', '<unknown>')}': business_key_unique_count must be an integer when provided. "
                    "Fix: set business_key_unique_count to a positive whole number or omit it."
                ) from exc
        cols = [ColumnSpec(**c) for c in t["columns"]]
        tables.append(
            TableSpec(
                table_name=t["table_name"],
                columns=cols,
                row_count=int(t.get("row_count", 100)),
                business_key=t.get("business_key"),
                business_key_unique_count=business_key_unique_count,
                business_key_static_columns=t.get("business_key_static_columns"),
                business_key_changing_columns=t.get("business_key_changing_columns"),
                scd_mode=t.get("scd_mode"),
                scd_tracked_columns=t.get("scd_tracked_columns"),
                scd_active_from_column=t.get("scd_active_from_column"),
                scd_active_to_column=t.get("scd_active_to_column"),
            )
        )

    fks = [ForeignKeySpec(**fk) for fk in data.get("foreign_keys", [])]

    project = SchemaProject(
        name=data["name"],
        seed=int(data.get("seed", 12345)),
        tables=tables,
        foreign_keys=fks,
    )
    validate_project(project)
    return project


def _normalize_sample_csv_paths(data: dict[str, object]) -> None:
    for table in data.get("tables", []):
        if not isinstance(table, dict):
            continue
        for column in table.get("columns", []):
            if not isinstance(column, dict):
                continue
            if column.get("generator") != "sample_csv":
                continue
            params = column.get("params")
            if not isinstance(params, dict):
                continue
            path_value = params.get("path")
            if not isinstance(path_value, str) or path_value.strip() == "":
                continue

            raw_path = path_value.strip()
            if raw_path == "__CITY_COUNTRY_CSV__":
                params["path"] = "tests/fixtures/city_country_pool.csv"
                continue
            params["path"] = to_repo_relative_path(raw_path)
