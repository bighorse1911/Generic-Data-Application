from __future__ import annotations

from src.schema.types import SEMANTIC_NUMERIC_TYPES
from src.schema.types import SUPPORTED_DTYPES
from src.schema.types import SchemaProject
from src.schema.validators.common import _validation_error


def validate_project_header_and_table_map(project: SchemaProject) -> dict[str, object]:
    if not project.name.strip():
        raise ValueError(
            _validation_error(
                "Project",
                "name cannot be empty",
                "set a non-empty project name",
            )
        )

    if not project.tables:
        raise ValueError(
            _validation_error(
                "Project",
                "must include at least one table",
                "add one or more tables before validation",
            )
        )

    # Unique table names
    table_names = [table.table_name.strip() for table in project.tables]
    if any(name == "" for name in table_names):
        raise ValueError(
            _validation_error(
                "Project tables",
                "table_name cannot be empty",
                "set a non-empty table_name for every table",
            )
        )
    if len(set(table_names)) != len(table_names):
        raise ValueError(
            _validation_error(
                "Project tables",
                "table names must be unique",
                "rename duplicate tables so each table_name is unique",
            )
        )

    table_map = {table.table_name: table for table in project.tables}
    return table_map


def validate_table_structure(table) -> dict[str, object]:
    if not table.columns:
        raise ValueError(
            _validation_error(
                f"Table '{table.table_name}'",
                "must have at least one column",
                "add one or more columns before validation",
            )
        )

    col_names = [column.name.strip() for column in table.columns]
    if any(name == "" for name in col_names):
        raise ValueError(
            _validation_error(
                f"Table '{table.table_name}'",
                "all column names must be non-empty",
                "set a non-empty name for every column",
            )
        )
    if len(set(col_names)) != len(col_names):
        raise ValueError(
            _validation_error(
                f"Table '{table.table_name}'",
                "column names must be unique",
                "rename duplicate columns so each column name is unique",
            )
        )
    col_map = {column.name: column for column in table.columns}

    pk_cols = [column for column in table.columns if column.primary_key]
    if len(pk_cols) > 1:
        raise ValueError(
            _validation_error(
                f"Table '{table.table_name}'",
                "only one primary key column is supported in this MVP",
                "keep exactly one column with primary_key=true",
            )
        )
    if len(pk_cols) == 0:
        raise ValueError(
            _validation_error(
                f"Table '{table.table_name}'",
                "must have a primary key column in this MVP",
                "mark one int column as primary_key=true",
            )
        )

    pk = pk_cols[0]
    if pk.dtype != "int":
        raise ValueError(
            _validation_error(
                f"Table '{table.table_name}', column '{pk.name}'",
                "primary key must be dtype=int in this MVP",
                "change the PK dtype to 'int'",
            )
        )

    return col_map


def validate_column_structural_rules(table, column) -> None:
    if column.dtype not in SUPPORTED_DTYPES:
        allowed = ", ".join(SUPPORTED_DTYPES)
        if column.dtype in SEMANTIC_NUMERIC_TYPES:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': unsupported dtype '{column.dtype}'. "
                f"Fix: use dtype='decimal' (or legacy 'float') with generator='{column.dtype}'. "
                f"Allowed dtypes: {allowed}."
            )
        raise ValueError(
            f"Table '{table.table_name}', column '{column.name}': unsupported dtype '{column.dtype}'. "
            f"Fix: use one of: {allowed}."
        )
    if column.choices is not None and len(column.choices) == 0:
        raise ValueError(
            _validation_error(
                f"Table '{table.table_name}', column '{column.name}'",
                "choices cannot be empty",
                "provide one or more choices or omit choices",
            )
        )
    if (column.min_value is not None) and (column.max_value is not None) and (column.min_value > column.max_value):
        raise ValueError(
            _validation_error(
                f"Table '{table.table_name}', column '{column.name}'",
                "min_value cannot exceed max_value",
                "set min_value <= max_value",
            )
        )
    if column.dtype == "bytes":
        if column.min_value is not None or column.max_value is not None:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': dtype 'bytes' does not support min_value/max_value. "
                "Fix: remove numeric bounds and use params.min_length/params.max_length for bytes length."
            )
        if column.choices is not None:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': dtype 'bytes' does not support choices. "
                "Fix: remove choices or use a bytes-compatible generator."
            )
        if column.pattern is not None:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': dtype 'bytes' does not support regex pattern. "
                "Fix: remove pattern or change dtype to 'text' for regex validation."
            )

        params = column.params or {}
        if not isinstance(params, dict):
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': dtype 'bytes' params must be a JSON object when provided. "
                "Fix: set params to an object like {\"min_length\": 8, \"max_length\": 16} or null."
            )
        min_len_raw = params.get("min_length", 8)
        max_len_raw = params.get("max_length", min_len_raw)
        try:
            min_len = int(min_len_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': dtype 'bytes' params.min_length must be an integer. "
                "Fix: set params.min_length to a whole number of bytes."
            ) from exc
        try:
            max_len = int(max_len_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': dtype 'bytes' params.max_length must be an integer. "
                "Fix: set params.max_length to a whole number of bytes."
            ) from exc
        if min_len < 0 or max_len < 0:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': dtype 'bytes' length bounds must be non-negative. "
                "Fix: set params.min_length and params.max_length to 0 or greater."
            )
        if min_len > max_len:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': dtype 'bytes' min_length cannot exceed max_length. "
                "Fix: set params.min_length <= params.max_length."
            )
    if column.generator is not None and column.params is not None and not isinstance(column.params, dict):
        raise ValueError(
            f"Table '{table.table_name}', column '{column.name}': generator params must be a JSON object. "
            "Fix: set params to an object (for example {\"path\": \"...\"}) or null."
        )


__all__ = [
    "validate_project_header_and_table_map",
    "validate_table_structure",
    "validate_column_structural_rules",
]
