from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

DataType = Literal["int", "float", "decimal", "text", "bool", "date", "datetime", "bytes"]

SUPPORTED_DTYPES: tuple[str, ...] = (
    "int",
    "float",
    "decimal",
    "text",
    "bool",
    "date",
    "datetime",
    "bytes",
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
    # optional target number of unique business-key combinations generated for this table
    business_key_unique_count: int | None = None
    # optional columns that must remain static across records for the same business key
    business_key_static_columns: list[str] | None = None
    # optional columns that are allowed to change across records for the same business key
    business_key_changing_columns: list[str] | None = None
    # optional SCD mode at table scope: "scd1" | "scd2"
    scd_mode: str | None = None
    # optional columns tracked by SCD logic
    scd_tracked_columns: list[str] | None = None
    # optional SCD active period columns (required for scd2)
    scd_active_from_column: str | None = None
    scd_active_to_column: str | None = None
    # optional deterministic correlation groups applied post-column generation
    correlation_groups: list[dict[str, object]] | None = None


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
    # optional DG05 parent attribute-aware weighted selection profile
    parent_selection: dict[str, object] | None = None
    # optional DG08 child-cardinality distribution profile
    child_count_distribution: dict[str, object] | None = None


@dataclass(frozen=True)
class SchemaProject:
    name: str
    seed: int = 12345
    tables: list[TableSpec] = field(default_factory=list)
    foreign_keys: list[ForeignKeySpec] = field(default_factory=list)
    timeline_constraints: list[dict[str, object]] | None = None
    data_quality_profiles: list[dict[str, object]] | None = None
    sample_profile_fits: list[dict[str, object]] | None = None
    locale_identity_bundles: list[dict[str, object]] | None = None


def _validation_error(location: str, issue: str, hint: str) -> str:
    return f"{location}: {issue}. Fix: {hint}."


def _is_scalar_json_value(value: object) -> bool:
    return not isinstance(value, (dict, list))


def _scalar_identity(value: object) -> tuple[str, str]:
    return (type(value).__name__, repr(value))


def _validate_fk_child_count_distribution(raw_profile: object, *, location: str) -> None:
    from src.schema.validators.fk import _validate_fk_child_count_distribution as _impl

    _impl(raw_profile, location=location)


def correlation_cholesky_lower(matrix: list[list[float]]) -> list[list[float]]:
    from src.schema.validators.correlation import correlation_cholesky_lower as _impl

    return _impl(matrix)


def _validate_correlation_groups_for_table(
    table: TableSpec,
    *,
    col_map: dict[str, ColumnSpec],
    incoming_fk_cols: set[str],
) -> None:
    from src.schema.validators.correlation import _validate_correlation_groups_for_table as _impl

    _impl(table, col_map=col_map, incoming_fk_cols=incoming_fk_cols)


def validate_project(project: SchemaProject) -> None:
    from src.schema.validate import validate_project as _validate_project

    _validate_project(project)
