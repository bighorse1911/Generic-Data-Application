"""Domain-first schema package exports."""

from src.schema.types import (
    DataType,
    SUPPORTED_DTYPES,
    SEMANTIC_NUMERIC_TYPES,
    ColumnSpec,
    TableSpec,
    ForeignKeySpec,
    SchemaProject,
)
from src.schema.validate import correlation_cholesky_lower, validate_project
from src.schema.validation_errors import validation_error

__all__ = [
    "DataType",
    "SUPPORTED_DTYPES",
    "SEMANTIC_NUMERIC_TYPES",
    "ColumnSpec",
    "TableSpec",
    "ForeignKeySpec",
    "SchemaProject",
    "correlation_cholesky_lower",
    "validate_project",
    "validation_error",
]
