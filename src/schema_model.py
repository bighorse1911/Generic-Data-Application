from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal

DataType = Literal["int", "float", "text", "bool", "date", "datetime"]

@dataclass(frozen=True)
class ColumnSpec:
    name: str
    dtype: DataType
    nullable: bool = True
    primary_key: bool = False
    unique: bool = False

    # constraints (optional)
    min_value: float | None = None
    max_value: float | None = None
    choices: list[str] | None = None
    pattern: str | None = None  # regex for text

@dataclass(frozen=True)
class TableSchema:
    table_name: str
    columns: list[ColumnSpec] = field(default_factory=list)
    seed: int = 12345

def validate_schema(schema: TableSchema) -> None:
    if not schema.table_name.strip():
        raise ValueError("Table name cannot be empty.")

    if not schema.columns:
        raise ValueError("Schema must contain at least one column.")

    names = [c.name.strip() for c in schema.columns]
    if any(n == "" for n in names):
        raise ValueError("All column names must be non-empty.")
    if len(set(names)) != len(names):
        raise ValueError("Column names must be unique.")

    pk_cols = [c for c in schema.columns if c.primary_key]
    if len(pk_cols) > 1:
        raise ValueError("Only one primary key column is supported in this MVP.")

    for c in schema.columns:
        if c.choices is not None and len(c.choices) == 0:
            raise ValueError(f"Column '{c.name}': choices cannot be empty.")
        if (c.min_value is not None) and (c.max_value is not None) and (c.min_value > c.max_value):
            raise ValueError(f"Column '{c.name}': min_value cannot exceed max_value.")
