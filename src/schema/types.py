"""Schema domain datatypes and immutable project specs."""

from src.schema.model_impl import (
    DataType,
    SUPPORTED_DTYPES,
    SEMANTIC_NUMERIC_TYPES,
    ColumnSpec,
    TableSpec,
    ForeignKeySpec,
    SchemaProject,
)

__all__ = [
    "DataType",
    "SUPPORTED_DTYPES",
    "SEMANTIC_NUMERIC_TYPES",
    "ColumnSpec",
    "TableSpec",
    "ForeignKeySpec",
    "SchemaProject",
]
