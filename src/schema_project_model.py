from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

DataType = Literal["int", "float", "text", "bool", "date", "datetime"]


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

        pk_cols = [c for c in t.columns if c.primary_key]
        if len(pk_cols) > 1:
            raise ValueError(f"Table '{t.table_name}': only one primary key column is supported in this MVP.")
        if len(pk_cols) == 0:
            raise ValueError(f"Table '{t.table_name}': must have a primary key column in this MVP.")

        pk = pk_cols[0]
        if pk.dtype != "int":
            raise ValueError(f"Table '{t.table_name}': primary key '{pk.name}' must be dtype=int in this MVP.")

        for c in t.columns:
            if c.choices is not None and len(c.choices) == 0:
                raise ValueError(
                    f"Table '{t.table_name}', column '{c.name}': choices cannot be empty."
                )
            if (c.min_value is not None) and (c.max_value is not None) and (c.min_value > c.max_value):
                raise ValueError(
                    f"Table '{t.table_name}', column '{c.name}': min_value cannot exceed max_value."
                )
        incoming = [fk for fk in project.foreign_keys if fk.child_table == t.table_name]

        # #We now allow for auto-sizing of children
        # if len(incoming) > 1 and t.row_count <= 0:
        #     raise ValueError(f"Table '{t.table_name}' has multiple FKs; set row_count > 0 (total rows).")

