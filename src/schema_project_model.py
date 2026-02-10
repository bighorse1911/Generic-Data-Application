from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

DataType = Literal["int", "float", "decimal", "text", "bool", "date", "datetime"]

SUPPORTED_DTYPES: tuple[str, ...] = (
    "int",
    "float",
    "decimal",
    "text",
    "bool",
    "date",
    "datetime",
)
SEMANTIC_NUMERIC_TYPES: tuple[str, ...] = ("latitude", "longitude", "money", "percent")


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    dtype: str
    nullable: bool = True
    primary_key: bool = False
    unique: bool = False
    min_value: float | None = None
    max_value: float | None = None
    choices: list[str] | None = None
    pattern: str | None = None

    # NEW
    generator: str | None = None
    params: dict[str, object] | None = None
    depends_on: list[str] | None = None


@dataclass(frozen=True)
class TableSpec:
    table_name: str
    columns: list[ColumnSpec] = field(default_factory=list)

    # generation hint: used ONLY for root tables (tables with no parent FK)
    row_count: int = 100
    # optional business key definition (supports composite keys)
    business_key: list[str] | None = None
    # optional SCD mode at table scope: "scd1" | "scd2"
    scd_mode: str | None = None
    # optional columns tracked by SCD logic
    scd_tracked_columns: list[str] | None = None
    # optional SCD active period columns (required for scd2)
    scd_active_from_column: str | None = None
    scd_active_to_column: str | None = None


@dataclass(frozen=True)
class ForeignKeySpec:
    # child side
    child_table: str
    child_column: str

    # parent side
    parent_table: str
    parent_column: str  # should be PK column in this MVP

    # generation rule: children per parent
    min_children: int = 1
    max_children: int = 3


@dataclass(frozen=True)
class SchemaProject:
    name: str
    seed: int = 12345
    tables: list[TableSpec] = field(default_factory=list)
    foreign_keys: list[ForeignKeySpec] = field(default_factory=list)


def validate_project(project: SchemaProject) -> None:
    if not project.name.strip():
        raise ValueError("Project name cannot be empty.")

    if not project.tables:
        raise ValueError("Project must include at least one table.")

    # Unique table names
    table_names = [t.table_name.strip() for t in project.tables]
    if any(n == "" for n in table_names):
        raise ValueError("All tables must have a non-empty table_name.")
    if len(set(table_names)) != len(table_names):
        raise ValueError("Table names must be unique.")

    table_map = {t.table_name: t for t in project.tables}

    # Per-table validations
    for t in project.tables:
 
        # # We now allow for auto-sizing of children
        # if t.row_count <= 0:
        #     raise ValueError(f"Table '{t.table_name}': row_count must be > 0.")

        if not t.columns:
            raise ValueError(f"Table '{t.table_name}': must have at least one column.")

        col_names = [c.name.strip() for c in t.columns]
        if any(n == "" for n in col_names):
            raise ValueError(f"Table '{t.table_name}': all column names must be non-empty.")
        if len(set(col_names)) != len(col_names):
            raise ValueError(f"Table '{t.table_name}': column names must be unique.")
        col_map = {c.name: c for c in t.columns}

        pk_cols = [c for c in t.columns if c.primary_key]
        if len(pk_cols) > 1:
            raise ValueError(f"Table '{t.table_name}': only one primary key column is supported in this MVP.")
        if len(pk_cols) == 0:
            raise ValueError(f"Table '{t.table_name}': must have a primary key column in this MVP.")

        pk = pk_cols[0]
        if pk.dtype != "int":
            raise ValueError(f"Table '{t.table_name}': primary key '{pk.name}' must be dtype=int in this MVP.")

        for c in t.columns:
            if c.dtype not in SUPPORTED_DTYPES:
                allowed = ", ".join(SUPPORTED_DTYPES)
                if c.dtype in SEMANTIC_NUMERIC_TYPES:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': unsupported dtype '{c.dtype}'. "
                        f"Fix: use dtype='decimal' (or legacy 'float') with generator='{c.dtype}'. "
                        f"Allowed dtypes: {allowed}."
                    )
                raise ValueError(
                    f"Table '{t.table_name}', column '{c.name}': unsupported dtype '{c.dtype}'. "
                    f"Fix: use one of: {allowed}."
                )
            if c.choices is not None and len(c.choices) == 0:
                raise ValueError(
                    f"Table '{t.table_name}', column '{c.name}': choices cannot be empty."
                )
            if (c.min_value is not None) and (c.max_value is not None) and (c.min_value > c.max_value):
                raise ValueError(
                    f"Table '{t.table_name}', column '{c.name}': min_value cannot exceed max_value."
                )
            if c.generator is not None and c.params is not None and not isinstance(c.params, dict):
                raise ValueError(
                    f"Table '{t.table_name}', column '{c.name}': generator params must be a JSON object. "
                    "Fix: set params to an object (for example {\"path\": \"...\"}) or null."
                )
            if c.generator == "sample_csv":
                params = c.params or {}
                path_value = params.get("path")
                if not isinstance(path_value, str) or path_value.strip() == "":
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'sample_csv' requires params.path. "
                        "Fix: set params.path to a CSV file path."
                    )
                path = path_value.strip()
                if not Path(path).exists():
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'sample_csv' params.path '{path}' does not exist. "
                        "Fix: provide an existing CSV file path."
                    )
                col_idx_value = params.get("column_index", 0)
                try:
                    col_idx = int(col_idx_value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'sample_csv' params.column_index must be an integer. "
                        "Fix: set params.column_index to 0 or greater."
                    ) from exc
                if col_idx < 0:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'sample_csv' params.column_index cannot be negative. "
                        "Fix: set params.column_index to 0 or greater."
                    )
        incoming = [fk for fk in project.foreign_keys if fk.child_table == t.table_name]
        incoming_fk_cols = {fk.child_column for fk in incoming}

        business_key = t.business_key
        if business_key is not None:
            if len(business_key) == 0:
                raise ValueError(
                    f"Table '{t.table_name}': business_key cannot be empty. "
                    "Fix: provide one or more existing column names or omit business_key."
                )
            for name in business_key:
                if name not in col_map:
                    raise ValueError(
                        f"Table '{t.table_name}': business_key column '{name}' not found. "
                        "Fix: use existing column names in business_key."
                    )
                c = col_map[name]
                if c.nullable:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{name}': business_key columns must be non-nullable. "
                        "Fix: set nullable=false for business_key columns."
                    )
                if c.dtype == "bool":
                    raise ValueError(
                        f"Table '{t.table_name}', column '{name}': dtype 'bool' is not supported for business_key. "
                        "Fix: use a stable business identifier column with dtype int/text/decimal/date/datetime."
                    )
                if name in incoming_fk_cols:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{name}': business_key cannot use incoming FK child column. "
                        "Fix: choose non-FK columns for business_key on child tables."
                    )

        scd_mode_raw = t.scd_mode.strip().lower() if isinstance(t.scd_mode, str) else ""
        scd_mode = scd_mode_raw or None
        if scd_mode not in {None, "scd1", "scd2"}:
            raise ValueError(
                f"Table '{t.table_name}': unsupported scd_mode '{t.scd_mode}'. "
                "Fix: use scd_mode='scd1' or scd_mode='scd2', or omit scd_mode."
            )

        has_scd_fields = any(
            [
                t.scd_tracked_columns is not None,
                t.scd_active_from_column is not None,
                t.scd_active_to_column is not None,
            ]
        )
        if scd_mode is None and has_scd_fields:
            raise ValueError(
                f"Table '{t.table_name}': SCD fields provided without scd_mode. "
                "Fix: set scd_mode='scd1' or scd_mode='scd2', or remove SCD fields."
            )

        if scd_mode is not None:
            if not business_key:
                raise ValueError(
                    f"Table '{t.table_name}': scd_mode='{scd_mode}' requires business_key. "
                    "Fix: define business_key columns before enabling SCD."
                )
            tracked = t.scd_tracked_columns or []
            if len(tracked) == 0:
                raise ValueError(
                    f"Table '{t.table_name}': scd_mode='{scd_mode}' requires non-empty scd_tracked_columns. "
                    "Fix: provide one or more existing column names in scd_tracked_columns."
                )
            for name in tracked:
                if name not in col_map:
                    raise ValueError(
                        f"Table '{t.table_name}': scd_tracked_columns includes unknown column '{name}'. "
                        "Fix: use existing column names in scd_tracked_columns."
                    )
                if business_key and name in business_key:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{name}': business_key columns cannot be in scd_tracked_columns. "
                        "Fix: track non-business-key columns for SCD changes."
                    )

            if scd_mode == "scd2":
                if incoming:
                    raise ValueError(
                        f"Table '{t.table_name}': scd_mode='scd2' is currently supported only on root tables. "
                        "Fix: remove incoming FKs or use scd_mode='scd1' for this table."
                    )
                start_col = t.scd_active_from_column
                end_col = t.scd_active_to_column
                if not start_col or not end_col:
                    raise ValueError(
                        f"Table '{t.table_name}': scd_mode='scd2' requires scd_active_from_column and scd_active_to_column. "
                        "Fix: set both columns to existing date or datetime columns."
                    )
                if start_col not in col_map or end_col not in col_map:
                    raise ValueError(
                        f"Table '{t.table_name}': SCD2 active period columns not found. "
                        "Fix: set scd_active_from_column/scd_active_to_column to existing columns."
                    )
                start_dtype = col_map[start_col].dtype
                end_dtype = col_map[end_col].dtype
                if start_dtype not in {"date", "datetime"} or end_dtype not in {"date", "datetime"}:
                    raise ValueError(
                        f"Table '{t.table_name}': SCD2 active period columns must be dtype date or datetime. "
                        "Fix: use date/datetime columns for scd_active_from_column and scd_active_to_column."
                    )
                if start_dtype != end_dtype:
                    raise ValueError(
                        f"Table '{t.table_name}': SCD2 active period column dtypes must match. "
                        "Fix: use the same dtype for scd_active_from_column and scd_active_to_column."
                    )
            elif scd_mode == "scd1":
                start_col = t.scd_active_from_column
                end_col = t.scd_active_to_column
                if start_col or end_col:
                    if not start_col or not end_col:
                        raise ValueError(
                            f"Table '{t.table_name}': SCD1 active period columns must be configured together. "
                            "Fix: set both scd_active_from_column and scd_active_to_column, or omit both."
                        )
                    if start_col not in col_map or end_col not in col_map:
                        raise ValueError(
                            f"Table '{t.table_name}': SCD1 active period columns not found. "
                            "Fix: set scd_active_from_column/scd_active_to_column to existing columns."
                        )
                    start_dtype = col_map[start_col].dtype
                    end_dtype = col_map[end_col].dtype
                    if start_dtype not in {"date", "datetime"} or end_dtype not in {"date", "datetime"}:
                        raise ValueError(
                            f"Table '{t.table_name}': SCD1 active period columns must be dtype date or datetime. "
                            "Fix: use date/datetime columns for scd_active_from_column and scd_active_to_column."
                        )
                    if start_dtype != end_dtype:
                        raise ValueError(
                            f"Table '{t.table_name}': SCD1 active period column dtypes must match. "
                            "Fix: use the same dtype for scd_active_from_column and scd_active_to_column."
                        )

        # #We now allow for auto-sizing of children
        # if len(incoming) > 1 and t.row_count <= 0:
        #     raise ValueError(f"Table '{t.table_name}' has multiple FKs; set row_count > 0 (total rows).")

    for fk in project.foreign_keys:
        if fk.child_table not in table_map:
            raise ValueError(
                f"Foreign key: child_table '{fk.child_table}' not found. "
                "Fix: use an existing table name for child_table."
            )
        if fk.parent_table not in table_map:
            raise ValueError(
                f"Foreign key: parent_table '{fk.parent_table}' not found. "
                "Fix: use an existing table name for parent_table."
            )

        child_table = table_map[fk.child_table]
        parent_table = table_map[fk.parent_table]
        child_cols = {c.name: c for c in child_table.columns}
        parent_cols = {c.name: c for c in parent_table.columns}

        if fk.child_column not in child_cols:
            raise ValueError(
                f"Foreign key on table '{fk.child_table}': child_column '{fk.child_column}' not found. "
                "Fix: use an existing child column."
            )
        if fk.parent_column not in parent_cols:
            raise ValueError(
                f"Foreign key on table '{fk.child_table}': parent_column '{fk.parent_column}' not found. "
                "Fix: use an existing parent column."
            )
        if not parent_cols[fk.parent_column].primary_key:
            raise ValueError(
                f"Foreign key on table '{fk.child_table}': parent column '{fk.parent_table}.{fk.parent_column}' must be primary key. "
                "Fix: reference the parent table primary key column."
            )
        if child_cols[fk.child_column].dtype != "int":
            raise ValueError(
                f"Foreign key on table '{fk.child_table}', column '{fk.child_column}': child FK column must be dtype int. "
                "Fix: use dtype='int' for FK child columns."
            )
        if fk.min_children <= 0 or fk.max_children <= 0:
            raise ValueError(
                f"Foreign key on table '{fk.child_table}': min_children and max_children must be > 0. "
                "Fix: set positive integer bounds."
            )
        if fk.min_children > fk.max_children:
            raise ValueError(
                f"Foreign key on table '{fk.child_table}': min_children cannot exceed max_children. "
                "Fix: set min_children <= max_children."
            )

