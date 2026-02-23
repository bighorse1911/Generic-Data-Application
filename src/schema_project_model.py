from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional
from src.project_paths import resolve_repo_path

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


@dataclass(frozen=True)
class SchemaProject:
    name: str
    seed: int = 12345
    tables: list[TableSpec] = field(default_factory=list)
    foreign_keys: list[ForeignKeySpec] = field(default_factory=list)
    timeline_constraints: list[dict[str, object]] | None = None


def _validation_error(location: str, issue: str, hint: str) -> str:
    return f"{location}: {issue}. Fix: {hint}."


def _is_scalar_json_value(value: object) -> bool:
    return not isinstance(value, (dict, list))


def _scalar_identity(value: object) -> tuple[str, str]:
    return (type(value).__name__, repr(value))


def correlation_cholesky_lower(matrix: list[list[float]]) -> list[list[float]]:
    """Return a lower-triangular factor for a positive semi-definite matrix."""
    size = len(matrix)
    lower: list[list[float]] = [[0.0 for _ in range(size)] for _ in range(size)]
    for row_idx in range(size):
        for col_idx in range(row_idx + 1):
            accum = 0.0
            for k in range(col_idx):
                accum += lower[row_idx][k] * lower[col_idx][k]
            if row_idx == col_idx:
                diagonal = matrix[row_idx][row_idx] - accum
                if diagonal < -1e-9:
                    raise ValueError("matrix is not positive semi-definite")
                lower[row_idx][col_idx] = (diagonal if diagonal > 0.0 else 0.0) ** 0.5
            else:
                pivot = lower[col_idx][col_idx]
                if abs(pivot) <= 1e-12:
                    lower[row_idx][col_idx] = 0.0
                else:
                    lower[row_idx][col_idx] = (matrix[row_idx][col_idx] - accum) / pivot
    return lower


def _validate_correlation_groups_for_table(
    table: TableSpec,
    *,
    col_map: dict[str, ColumnSpec],
    incoming_fk_cols: set[str],
) -> None:
    groups = table.correlation_groups
    if groups is None:
        return
    if not isinstance(groups, list):
        raise ValueError(
            _validation_error(
                f"Table '{table.table_name}'",
                "correlation_groups must be a list when provided",
                "set correlation_groups to a list of group objects or omit correlation_groups",
            )
        )
    if len(groups) == 0:
        raise ValueError(
            _validation_error(
                f"Table '{table.table_name}'",
                "correlation_groups cannot be empty when provided",
                "add one or more correlation groups or omit correlation_groups",
            )
        )

    seen_group_ids: set[str] = set()
    claimed_columns: dict[str, str] = {}
    business_key_cols = set(table.business_key or [])
    depends_on_by_column = {column.name: set(column.depends_on or []) for column in table.columns}

    for group_index, group in enumerate(groups):
        location = f"Table '{table.table_name}', correlation_groups[{group_index}]"
        if not isinstance(group, dict):
            raise ValueError(
                _validation_error(
                    location,
                    "group must be a JSON object",
                    "configure this correlation group as an object with group_id, columns, and rank_correlation",
                )
            )

        group_id_raw = group.get("group_id")
        if not isinstance(group_id_raw, str) or group_id_raw.strip() == "":
            raise ValueError(
                _validation_error(
                    location,
                    "group_id is required",
                    "set group_id to a non-empty string",
                )
            )
        group_id = group_id_raw.strip()
        if group_id in seen_group_ids:
            raise ValueError(
                _validation_error(
                    f"Table '{table.table_name}'",
                    f"duplicate correlation group_id '{group_id}'",
                    "use unique group_id values in correlation_groups",
                )
            )
        seen_group_ids.add(group_id)

        columns_raw = group.get("columns")
        if not isinstance(columns_raw, list) or len(columns_raw) < 2:
            raise ValueError(
                _validation_error(
                    location,
                    "columns must be a list with at least two column names",
                    "set columns to two or more existing non-key columns",
                )
            )
        columns: list[str] = []
        for column_raw in columns_raw:
            if not isinstance(column_raw, str) or column_raw.strip() == "":
                raise ValueError(
                    _validation_error(
                        location,
                        "columns contains an empty or non-string value",
                        "use non-empty column-name strings in columns",
                    )
                )
            columns.append(column_raw.strip())
        if len(set(columns)) != len(columns):
            raise ValueError(
                _validation_error(
                    location,
                    "columns contains duplicate names",
                    "list each correlation column only once",
                )
            )

        for column_name in columns:
            existing_group = claimed_columns.get(column_name)
            if existing_group is not None:
                raise ValueError(
                    _validation_error(
                        f"Table '{table.table_name}', column '{column_name}'",
                        f"is already assigned to correlation group '{existing_group}'",
                        "assign each column to at most one correlation group",
                    )
                )
            if column_name not in col_map:
                raise ValueError(
                    _validation_error(
                        location,
                        f"column '{column_name}' was not found",
                        "use existing column names in correlation_groups.columns",
                    )
                )
            column = col_map[column_name]
            if column.primary_key:
                raise ValueError(
                    _validation_error(
                        f"Table '{table.table_name}', column '{column_name}'",
                        "primary key columns cannot be in correlation groups",
                        "choose non-primary-key columns for correlation",
                    )
                )
            if column_name in incoming_fk_cols:
                raise ValueError(
                    _validation_error(
                        f"Table '{table.table_name}', column '{column_name}'",
                        "child foreign-key columns cannot be in correlation groups",
                        "choose non-FK columns for correlation",
                    )
                )
            if column_name in business_key_cols:
                raise ValueError(
                    _validation_error(
                        f"Table '{table.table_name}', column '{column_name}'",
                        "business_key columns cannot be in correlation groups",
                        "choose non-business-key columns for correlation",
                    )
                )
            if column.dtype == "bytes":
                raise ValueError(
                    _validation_error(
                        f"Table '{table.table_name}', column '{column_name}'",
                        "dtype 'bytes' is not supported in correlation groups",
                        "use numeric, text, bool, date, or datetime columns for correlation",
                    )
                )
            if len(column.depends_on or []) > 0:
                raise ValueError(
                    _validation_error(
                        f"Table '{table.table_name}', column '{column_name}'",
                        "columns with depends_on cannot be in correlation groups",
                        "remove depends_on from this column or exclude it from correlation_groups",
                    )
                )
            claimed_columns[column_name] = group_id

        for target_column, depends_on in depends_on_by_column.items():
            overlap = sorted(set(columns) & depends_on)
            if overlap:
                overlap_display = ", ".join(overlap)
                raise ValueError(
                    _validation_error(
                        location,
                        f"columns ({overlap_display}) are referenced by depends_on in column '{target_column}'",
                        "remove depends_on relationships involving correlation-group columns",
                    )
                )

        rank_raw = group.get("rank_correlation")
        expected_size = len(columns)
        if not isinstance(rank_raw, list) or len(rank_raw) != expected_size:
            raise ValueError(
                _validation_error(
                    location,
                    f"rank_correlation must be a {expected_size}x{expected_size} matrix",
                    "set rank_correlation rows/columns to match the columns list length",
                )
            )
        rank_matrix: list[list[float]] = []
        for row_index, row_raw in enumerate(rank_raw):
            if not isinstance(row_raw, list) or len(row_raw) != expected_size:
                raise ValueError(
                    _validation_error(
                        location,
                        f"rank_correlation row {row_index} must contain {expected_size} entries",
                        "set each rank_correlation row length to match the columns list length",
                    )
                )
            parsed_row: list[float] = []
            for col_index, value_raw in enumerate(row_raw):
                try:
                    value = float(value_raw)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        _validation_error(
                            location,
                            f"rank_correlation[{row_index}][{col_index}] must be numeric",
                            "use numeric correlation coefficients between -1 and 1",
                        )
                    ) from exc
                if value < -1.0 or value > 1.0:
                    raise ValueError(
                        _validation_error(
                            location,
                            f"rank_correlation[{row_index}][{col_index}]={value} is outside [-1, 1]",
                            "keep all correlation coefficients within -1 and 1",
                        )
                    )
                parsed_row.append(value)
            rank_matrix.append(parsed_row)

        for diag_index in range(expected_size):
            diagonal = rank_matrix[diag_index][diag_index]
            if abs(diagonal - 1.0) > 1e-6:
                raise ValueError(
                    _validation_error(
                        location,
                        f"rank_correlation diagonal at [{diag_index}][{diag_index}] must be 1.0",
                        "set all diagonal entries to 1.0",
                    )
                )
        for row_index in range(expected_size):
            for col_index in range(row_index + 1, expected_size):
                left = rank_matrix[row_index][col_index]
                right = rank_matrix[col_index][row_index]
                if abs(left - right) > 1e-6:
                    raise ValueError(
                        _validation_error(
                            location,
                            f"rank_correlation must be symmetric but [{row_index}][{col_index}]={left} and [{col_index}][{row_index}]={right}",
                            "set rank_correlation to a symmetric matrix",
                        )
                    )
        try:
            correlation_cholesky_lower(rank_matrix)
        except ValueError as exc:
            raise ValueError(
                _validation_error(
                    location,
                    "rank_correlation must be positive semi-definite",
                    "adjust coefficients to a valid correlation matrix",
                )
            ) from exc

        strength_raw = group.get("strength", 1.0)
        try:
            strength = float(strength_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _validation_error(
                    location,
                    "strength must be numeric when provided",
                    "set strength to a numeric value between 0 and 1",
                )
            ) from exc
        if strength < 0.0 or strength > 1.0:
            raise ValueError(
                _validation_error(
                    location,
                    f"strength {strength} is outside [0, 1]",
                    "set strength to a value between 0 and 1",
                )
            )

        categorical_orders_raw = group.get("categorical_orders")
        if categorical_orders_raw is not None:
            if not isinstance(categorical_orders_raw, dict):
                raise ValueError(
                    _validation_error(
                        location,
                        "categorical_orders must be an object when provided",
                        "set categorical_orders to an object mapping column names to ordered scalar lists",
                    )
                )
            for order_column_raw, order_values_raw in categorical_orders_raw.items():
                if not isinstance(order_column_raw, str) or order_column_raw.strip() == "":
                    raise ValueError(
                        _validation_error(
                            location,
                            "categorical_orders contains an empty or non-string column key",
                            "use non-empty column names as categorical_orders keys",
                        )
                    )
                order_column = order_column_raw.strip()
                if order_column not in columns:
                    raise ValueError(
                        _validation_error(
                            location,
                            f"categorical_orders key '{order_column}' must also be listed in columns",
                            "add the column to this group's columns list or remove the categorical_orders key",
                        )
                    )
                if not isinstance(order_values_raw, list) or len(order_values_raw) == 0:
                    raise ValueError(
                        _validation_error(
                            location,
                            f"categorical_orders['{order_column}'] must be a non-empty list",
                            "provide one or more ordered scalar values for this column",
                        )
                    )
                seen_values: set[tuple[str, str]] = set()
                for value in order_values_raw:
                    if not _is_scalar_json_value(value):
                        raise ValueError(
                            _validation_error(
                                location,
                                f"categorical_orders['{order_column}'] values must be scalar",
                                "use scalar values (string/number/bool/null) in categorical_orders",
                            )
                        )
                    marker = _scalar_identity(value)
                    if marker in seen_values:
                        raise ValueError(
                            _validation_error(
                                location,
                                f"categorical_orders['{order_column}'] contains duplicate values",
                                "list each ordered categorical value only once",
                            )
                        )
                    seen_values.add(marker)


def validate_project(project: SchemaProject) -> None:
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
    table_names = [t.table_name.strip() for t in project.tables]
    if any(n == "" for n in table_names):
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

    table_map = {t.table_name: t for t in project.tables}

    def _parse_float_param(
        params: dict[str, object],
        key: str,
        *,
        location: str,
        hint: str,
        default: float | None = None,
        required: bool = False,
    ) -> float | None:
        raw: object | None
        if key in params:
            raw = params.get(key)
        else:
            raw = default
        if raw is None:
            if required:
                raise ValueError(
                    f"{location}: params.{key} is required. "
                    f"Fix: {hint}."
                )
            return None
        try:
            return float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{location}: params.{key} must be numeric. "
                f"Fix: {hint}."
            ) from exc

    def _parse_int_param(
        params: dict[str, object],
        key: str,
        *,
        location: str,
        hint: str,
        default: int | None = None,
        required: bool = False,
    ) -> int | None:
        raw: object | None
        if key in params:
            raw = params.get(key)
        else:
            raw = default
        if raw is None:
            if required:
                raise ValueError(
                    f"{location}: params.{key} is required. "
                    f"Fix: {hint}."
                )
            return None
        try:
            return int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{location}: params.{key} must be an integer. "
                f"Fix: {hint}."
            ) from exc

    def _parse_non_negative_int(
        value: object,
        *,
        location: str,
        field_name: str,
        hint: str,
    ) -> int:
        if isinstance(value, bool):
            raise ValueError(
                _validation_error(
                    location,
                    f"{field_name} must be an integer",
                    hint,
                )
            )
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _validation_error(
                    location,
                    f"{field_name} must be an integer",
                    hint,
                )
            ) from exc
        if parsed < 0:
            raise ValueError(
                _validation_error(
                    location,
                    f"{field_name} cannot be negative",
                    hint,
                )
            )
        return parsed

    # Per-table validations
    for t in project.tables:
 
        # # We now allow for auto-sizing of children
        # if t.row_count <= 0:
        #     raise ValueError(f"Table '{t.table_name}': row_count must be > 0.")

        if not t.columns:
            raise ValueError(
                _validation_error(
                    f"Table '{t.table_name}'",
                    "must have at least one column",
                    "add one or more columns before validation",
                )
            )

        col_names = [c.name.strip() for c in t.columns]
        if any(n == "" for n in col_names):
            raise ValueError(
                _validation_error(
                    f"Table '{t.table_name}'",
                    "all column names must be non-empty",
                    "set a non-empty name for every column",
                )
            )
        if len(set(col_names)) != len(col_names):
            raise ValueError(
                _validation_error(
                    f"Table '{t.table_name}'",
                    "column names must be unique",
                    "rename duplicate columns so each column name is unique",
                )
            )
        col_map = {c.name: c for c in t.columns}

        pk_cols = [c for c in t.columns if c.primary_key]
        if len(pk_cols) > 1:
            raise ValueError(
                _validation_error(
                    f"Table '{t.table_name}'",
                    "only one primary key column is supported in this MVP",
                    "keep exactly one column with primary_key=true",
                )
            )
        if len(pk_cols) == 0:
            raise ValueError(
                _validation_error(
                    f"Table '{t.table_name}'",
                    "must have a primary key column in this MVP",
                    "mark one int column as primary_key=true",
                )
            )

        pk = pk_cols[0]
        if pk.dtype != "int":
            raise ValueError(
                _validation_error(
                    f"Table '{t.table_name}', column '{pk.name}'",
                    "primary key must be dtype=int in this MVP",
                    "change the PK dtype to 'int'",
                )
            )

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
                    _validation_error(
                        f"Table '{t.table_name}', column '{c.name}'",
                        "choices cannot be empty",
                        "provide one or more choices or omit choices",
                    )
                )
            if (c.min_value is not None) and (c.max_value is not None) and (c.min_value > c.max_value):
                raise ValueError(
                    _validation_error(
                        f"Table '{t.table_name}', column '{c.name}'",
                        "min_value cannot exceed max_value",
                        "set min_value <= max_value",
                    )
                )
            if c.dtype == "bytes":
                if c.min_value is not None or c.max_value is not None:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': dtype 'bytes' does not support min_value/max_value. "
                        "Fix: remove numeric bounds and use params.min_length/params.max_length for bytes length."
                    )
                if c.choices is not None:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': dtype 'bytes' does not support choices. "
                        "Fix: remove choices or use a bytes-compatible generator."
                    )
                if c.pattern is not None:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': dtype 'bytes' does not support regex pattern. "
                        "Fix: remove pattern or change dtype to 'text' for regex validation."
                    )

                params = c.params or {}
                if not isinstance(params, dict):
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': dtype 'bytes' params must be a JSON object when provided. "
                        "Fix: set params to an object like {\"min_length\": 8, \"max_length\": 16} or null."
                    )
                min_len_raw = params.get("min_length", 8)
                max_len_raw = params.get("max_length", min_len_raw)
                try:
                    min_len = int(min_len_raw)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': dtype 'bytes' params.min_length must be an integer. "
                        "Fix: set params.min_length to a whole number of bytes."
                    ) from exc
                try:
                    max_len = int(max_len_raw)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': dtype 'bytes' params.max_length must be an integer. "
                        "Fix: set params.max_length to a whole number of bytes."
                    ) from exc
                if min_len < 0 or max_len < 0:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': dtype 'bytes' length bounds must be non-negative. "
                        "Fix: set params.min_length and params.max_length to 0 or greater."
                    )
                if min_len > max_len:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': dtype 'bytes' min_length cannot exceed max_length. "
                        "Fix: set params.min_length <= params.max_length."
                    )
            if c.generator is not None and c.params is not None and not isinstance(c.params, dict):
                raise ValueError(
                    f"Table '{t.table_name}', column '{c.name}': generator params must be a JSON object. "
                    "Fix: set params to an object (for example {\"path\": \"...\"}) or null."
                )
            if c.generator == "uniform_int":
                if c.dtype != "int":
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'uniform_int' requires dtype int. "
                        "Fix: set dtype='int' or use 'uniform_float'/'normal' for decimal-like values."
                    )
                params = c.params or {}
                location = f"Table '{t.table_name}', column '{c.name}': generator 'uniform_int'"
                min_v = _parse_int_param(
                    params,
                    "min",
                    location=location,
                    hint="set params.min to a whole-number lower bound",
                    default=0,
                )
                max_v = _parse_int_param(
                    params,
                    "max",
                    location=location,
                    hint="set params.max to a whole-number upper bound",
                    default=100,
                )
                if min_v is not None and max_v is not None and min_v > max_v:
                    raise ValueError(
                        f"{location}: params.max cannot be less than params.min. "
                        "Fix: set params.max >= params.min."
                    )
            if c.generator == "uniform_float":
                if c.dtype not in {"float", "decimal"}:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'uniform_float' requires dtype decimal or legacy float. "
                        "Fix: set dtype='decimal' for new numeric columns."
                    )
                params = c.params or {}
                location = f"Table '{t.table_name}', column '{c.name}': generator 'uniform_float'"
                min_v = _parse_float_param(
                    params,
                    "min",
                    location=location,
                    hint="set params.min to a numeric lower bound",
                    default=0.0,
                )
                max_v = _parse_float_param(
                    params,
                    "max",
                    location=location,
                    hint="set params.max to a numeric upper bound",
                    default=1.0,
                )
                decimals = _parse_int_param(
                    params,
                    "decimals",
                    location=location,
                    hint="set params.decimals to 0 or greater",
                    default=3,
                )
                if decimals is not None and decimals < 0:
                    raise ValueError(
                        f"{location}: params.decimals must be >= 0. "
                        "Fix: set params.decimals to 0 or greater."
                    )
                if min_v is not None and max_v is not None and min_v > max_v:
                    raise ValueError(
                        f"{location}: params.max cannot be less than params.min. "
                        "Fix: set params.max >= params.min."
                    )
            if c.generator == "normal":
                if c.dtype not in {"int", "float", "decimal"}:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'normal' requires dtype int, decimal, or legacy float. "
                        "Fix: change dtype to int/decimal or choose a text-compatible generator."
                    )
                params = c.params or {}
                location = f"Table '{t.table_name}', column '{c.name}': generator 'normal'"
                _parse_float_param(
                    params,
                    "mean",
                    location=location,
                    hint="set params.mean to a numeric average value",
                    default=0.0,
                )
                has_stdev = "stdev" in params
                has_stddev = "stddev" in params
                if has_stdev and has_stddev:
                    raise ValueError(
                        f"{location}: params.stdev and params.stddev cannot both be set. "
                        "Fix: provide only one standard deviation key."
                    )
                stdev_key = "stddev" if has_stddev else "stdev"
                stdev = _parse_float_param(
                    params,
                    stdev_key,
                    location=location,
                    hint=f"set params.{stdev_key} to a positive number",
                    default=1.0,
                )
                if stdev is not None and stdev <= 0:
                    raise ValueError(
                        f"{location}: params.{stdev_key} must be > 0. "
                        f"Fix: set params.{stdev_key} to a positive number."
                    )
                decimals = _parse_int_param(
                    params,
                    "decimals",
                    location=location,
                    hint="set params.decimals to 0 or greater",
                    default=2,
                )
                if decimals is not None and decimals < 0:
                    raise ValueError(
                        f"{location}: params.decimals must be >= 0. "
                        "Fix: set params.decimals to 0 or greater."
                    )
                min_v = _parse_float_param(
                    params,
                    "min",
                    location=location,
                    hint="set params.min to a numeric lower bound or omit it",
                )
                max_v = _parse_float_param(
                    params,
                    "max",
                    location=location,
                    hint="set params.max to a numeric upper bound or omit it",
                )
                if min_v is not None and max_v is not None and min_v > max_v:
                    raise ValueError(
                        f"{location}: params.max cannot be less than params.min. "
                        "Fix: set params.max >= params.min."
                    )
            if c.generator == "lognormal":
                if c.dtype not in {"int", "float", "decimal"}:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'lognormal' requires dtype int, decimal, or legacy float. "
                        "Fix: change dtype to int/decimal or choose a text-compatible generator."
                    )
                params = c.params or {}
                location = f"Table '{t.table_name}', column '{c.name}': generator 'lognormal'"
                median = _parse_float_param(
                    params,
                    "median",
                    location=location,
                    hint="set params.median to a positive number",
                    default=50000.0,
                )
                sigma = _parse_float_param(
                    params,
                    "sigma",
                    location=location,
                    hint="set params.sigma to a positive number",
                    default=0.5,
                )
                if median is not None and median <= 0:
                    raise ValueError(
                        f"{location}: params.median must be > 0. "
                        "Fix: set params.median to a positive number."
                    )
                if sigma is not None and sigma <= 0:
                    raise ValueError(
                        f"{location}: params.sigma must be > 0. "
                        "Fix: set params.sigma to a positive number."
                    )
                decimals = _parse_int_param(
                    params,
                    "decimals",
                    location=location,
                    hint="set params.decimals to 0 or greater",
                    default=2,
                )
                if decimals is not None and decimals < 0:
                    raise ValueError(
                        f"{location}: params.decimals must be >= 0. "
                        "Fix: set params.decimals to 0 or greater."
                    )
                min_v = _parse_float_param(
                    params,
                    "min",
                    location=location,
                    hint="set params.min to a numeric lower bound or omit it",
                )
                max_v = _parse_float_param(
                    params,
                    "max",
                    location=location,
                    hint="set params.max to a numeric upper bound or omit it",
                )
                if min_v is not None and max_v is not None and min_v > max_v:
                    raise ValueError(
                        f"{location}: params.max cannot be less than params.min. "
                        "Fix: set params.max >= params.min."
                    )
            if c.generator == "choice_weighted":
                if c.dtype not in {"text", "int"}:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'choice_weighted' requires dtype text or int. "
                        "Fix: change dtype to text/int or choose a generator compatible with this dtype."
                    )
                params = c.params or {}
                location = f"Table '{t.table_name}', column '{c.name}': generator 'choice_weighted'"
                choices = params.get("choices")
                if not isinstance(choices, list) or len(choices) == 0:
                    raise ValueError(
                        f"{location}: params.choices must be a non-empty list. "
                        "Fix: provide one or more values in params.choices."
                    )
                weights = params.get("weights")
                if weights is not None:
                    if not isinstance(weights, list) or len(weights) != len(choices):
                        raise ValueError(
                            f"{location}: params.weights must match params.choices length. "
                            "Fix: provide one numeric weight per choice or omit params.weights."
                        )
                    parsed_weights: list[float] = []
                    for idx, weight in enumerate(weights):
                        try:
                            weight_num = float(weight)
                        except (TypeError, ValueError) as exc:
                            raise ValueError(
                                f"{location}: params.weights[{idx}] must be numeric. "
                                "Fix: provide numeric weights (for example 0.2, 1, 3.5)."
                            ) from exc
                        if weight_num < 0:
                            raise ValueError(
                                f"{location}: params.weights[{idx}] cannot be negative. "
                                "Fix: use weights >= 0 and keep at least one value > 0."
                            )
                        parsed_weights.append(weight_num)
                    if not any(w > 0 for w in parsed_weights):
                        raise ValueError(
                            f"{location}: params.weights must include at least one value > 0. "
                            "Fix: set one or more weights above zero."
                        )
            if c.generator == "ordered_choice":
                if c.dtype not in {"text", "int"}:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'ordered_choice' requires dtype text or int. "
                        "Fix: change dtype to text/int or choose a generator compatible with this dtype."
                    )
                params = c.params or {}
                location = f"Table '{t.table_name}', column '{c.name}': generator 'ordered_choice'"
                orders_raw = params.get("orders")
                if not isinstance(orders_raw, dict) or len(orders_raw) == 0:
                    raise ValueError(
                        f"{location}: params.orders must be a non-empty object. "
                        "Fix: set params.orders to a mapping like {'A': ['one', 'two'], 'B': ['three', 'four']}."
                    )

                normalized_orders: dict[str, list[object]] = {}
                for raw_name, raw_values in orders_raw.items():
                    if not isinstance(raw_name, str) or raw_name.strip() == "":
                        raise ValueError(
                            f"{location}: params.orders keys must be non-empty strings. "
                            "Fix: use order names like 'A' or 'OrderB' as object keys."
                        )
                    order_name = raw_name.strip()
                    if order_name in normalized_orders:
                        raise ValueError(
                            f"{location}: duplicate order key '{order_name}' after normalization. "
                            "Fix: use unique order names in params.orders."
                        )
                    if not isinstance(raw_values, list) or len(raw_values) == 0:
                        raise ValueError(
                            f"{location}: params.orders['{order_name}'] must be a non-empty list. "
                            "Fix: provide one or more ordered values per order."
                        )
                    for idx, value in enumerate(raw_values):
                        if isinstance(value, (dict, list)):
                            raise ValueError(
                                f"{location}: params.orders['{order_name}'][{idx}] must be a scalar value. "
                                "Fix: use string/number/bool/null values in order lists."
                            )
                    normalized_orders[order_name] = raw_values

                order_names = list(normalized_orders.keys())
                order_weights_raw = params.get("order_weights")
                if order_weights_raw is not None:
                    if not isinstance(order_weights_raw, dict):
                        raise ValueError(
                            f"{location}: params.order_weights must be an object when provided. "
                            "Fix: set params.order_weights like {'A': 0.7, 'B': 0.3}."
                        )
                    missing_orders = [name for name in order_names if name not in order_weights_raw]
                    extra_orders = [name for name in order_weights_raw.keys() if name not in normalized_orders]
                    if missing_orders or extra_orders:
                        missing_text = ", ".join(missing_orders) if missing_orders else "(none)"
                        extra_text = ", ".join(str(name) for name in extra_orders) if extra_orders else "(none)"
                        raise ValueError(
                            f"{location}: params.order_weights keys must exactly match params.orders keys (missing: {missing_text}; extra: {extra_text}). "
                            "Fix: add one weight per order and remove unknown order_weights keys."
                        )
                    parsed_order_weights: list[float] = []
                    for order_name in order_names:
                        raw_weight = order_weights_raw.get(order_name)
                        try:
                            weight = float(raw_weight)
                        except (TypeError, ValueError) as exc:
                            raise ValueError(
                                f"{location}: params.order_weights['{order_name}'] must be numeric. "
                                "Fix: provide numeric order weights (for example 0.2, 1, 3.5)."
                            ) from exc
                        if weight < 0:
                            raise ValueError(
                                f"{location}: params.order_weights['{order_name}'] cannot be negative. "
                                "Fix: use non-negative order weights and keep at least one value > 0."
                            )
                        parsed_order_weights.append(weight)
                    if not any(weight > 0 for weight in parsed_order_weights):
                        raise ValueError(
                            f"{location}: params.order_weights must include at least one value > 0. "
                            "Fix: set one or more order weights above zero."
                        )

                move_weights_raw = params.get("move_weights", [0.0, 1.0])
                if not isinstance(move_weights_raw, list) or len(move_weights_raw) == 0:
                    raise ValueError(
                        f"{location}: params.move_weights must be a non-empty list. "
                        "Fix: set params.move_weights to one or more numeric step weights."
                    )
                parsed_move_weights: list[float] = []
                for idx, raw_weight in enumerate(move_weights_raw):
                    try:
                        weight = float(raw_weight)
                    except (TypeError, ValueError) as exc:
                        raise ValueError(
                            f"{location}: params.move_weights[{idx}] must be numeric. "
                            "Fix: use numeric move weights (for example [0.1, 0.8, 0.1])."
                        ) from exc
                    if weight < 0:
                        raise ValueError(
                            f"{location}: params.move_weights[{idx}] cannot be negative. "
                            "Fix: use non-negative move weights and keep at least one value > 0."
                        )
                    parsed_move_weights.append(weight)
                if not any(weight > 0 for weight in parsed_move_weights):
                    raise ValueError(
                        f"{location}: params.move_weights must include at least one value > 0. "
                        "Fix: set one or more move weights above zero."
                    )

                start_index_raw = params.get("start_index", 0)
                try:
                    start_index = int(start_index_raw)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"{location}: params.start_index must be an integer. "
                        "Fix: set params.start_index to 0 or greater."
                    ) from exc
                if start_index < 0:
                    raise ValueError(
                        f"{location}: params.start_index cannot be negative. "
                        "Fix: set params.start_index to 0 or greater."
                    )
                for order_name, order_values in normalized_orders.items():
                    if start_index >= len(order_values):
                        raise ValueError(
                            f"{location}: params.start_index={start_index} is outside order '{order_name}' length {len(order_values)}. "
                            "Fix: set params.start_index within every configured order length."
                        )
            if c.generator == "state_transition":
                if c.dtype not in {"text", "int"}:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'state_transition' requires dtype text or int. "
                        "Fix: change dtype to text/int or choose a generator compatible with this dtype."
                    )
                params = c.params or {}
                location = f"Table '{t.table_name}', column '{c.name}': generator 'state_transition'"

                entity_col_raw = params.get("entity_column")
                if not isinstance(entity_col_raw, str) or entity_col_raw.strip() == "":
                    raise ValueError(
                        f"{location}: params.entity_column is required. "
                        "Fix: set params.entity_column to an existing source column name."
                    )
                entity_col = entity_col_raw.strip()
                if entity_col == c.name:
                    raise ValueError(
                        f"{location}: params.entity_column cannot reference the target column itself. "
                        "Fix: choose a different source column for entity identity."
                    )
                if entity_col not in col_map:
                    raise ValueError(
                        f"{location}: params.entity_column '{entity_col}' was not found. "
                        "Fix: use an existing source column name."
                    )
                depends_on = c.depends_on or []
                if entity_col not in depends_on:
                    raise ValueError(
                        f"{location}: requires depends_on to include '{entity_col}'. "
                        "Fix: add the entity source column to depends_on so it generates first."
                    )

                states_raw = params.get("states")
                if not isinstance(states_raw, list) or len(states_raw) == 0:
                    raise ValueError(
                        f"{location}: params.states must be a non-empty list. "
                        "Fix: provide one or more allowed state values."
                    )

                states: list[object] = []
                state_identities: set[tuple[str, str]] = set()
                for idx, raw_state in enumerate(states_raw):
                    if isinstance(raw_state, (dict, list)) or isinstance(raw_state, bool):
                        raise ValueError(
                            f"{location}: params.states[{idx}] must be a scalar text/int value. "
                            "Fix: use only string or integer states."
                        )
                    if c.dtype == "text":
                        if not isinstance(raw_state, str) or raw_state.strip() == "":
                            raise ValueError(
                                f"{location}: params.states[{idx}] must be a non-empty string for dtype text. "
                                "Fix: use non-empty string states when dtype='text'."
                            )
                        normalized_state: object = raw_state
                    else:
                        if not isinstance(raw_state, int):
                            raise ValueError(
                                f"{location}: params.states[{idx}] must be an integer for dtype int. "
                                "Fix: use integer states when dtype='int'."
                            )
                        normalized_state = int(raw_state)
                    identity = _scalar_identity(normalized_state)
                    if identity in state_identities:
                        raise ValueError(
                            f"{location}: params.states contains duplicate values. "
                            "Fix: list each state only once."
                        )
                    state_identities.add(identity)
                    states.append(normalized_state)

                state_set = set(states)

                def _coerce_state_ref(
                    raw_value: object,
                    *,
                    field_name: str,
                    allow_int_string: bool,
                ) -> object:
                    if c.dtype == "text":
                        if not isinstance(raw_value, str):
                            raise ValueError(
                                f"{location}: {field_name} must reference text states. "
                                "Fix: use string state values declared in params.states."
                            )
                        normalized = raw_value
                    else:
                        if isinstance(raw_value, bool):
                            raise ValueError(
                                f"{location}: {field_name} must reference integer states. "
                                "Fix: use integer state values declared in params.states."
                            )
                        if isinstance(raw_value, int):
                            normalized = int(raw_value)
                        elif allow_int_string and isinstance(raw_value, str) and raw_value.strip() != "":
                            try:
                                normalized = int(raw_value.strip())
                            except (TypeError, ValueError) as exc:
                                raise ValueError(
                                    f"{location}: {field_name} value '{raw_value}' is not a valid integer state. "
                                    "Fix: use integer state values declared in params.states."
                                ) from exc
                        else:
                            raise ValueError(
                                f"{location}: {field_name} must reference integer states. "
                                "Fix: use integer state values declared in params.states."
                            )
                    if normalized not in state_set:
                        raise ValueError(
                            f"{location}: {field_name} value '{normalized}' is not in params.states. "
                            "Fix: reference only states declared in params.states."
                        )
                    return normalized

                start_state_raw = params.get("start_state")
                start_weights_raw = params.get("start_weights")
                if start_state_raw is not None and start_weights_raw is not None:
                    raise ValueError(
                        f"{location}: params.start_state and params.start_weights cannot both be set. "
                        "Fix: configure either a fixed start_state or weighted start_weights."
                    )
                if start_state_raw is not None:
                    _coerce_state_ref(
                        start_state_raw,
                        field_name="params.start_state",
                        allow_int_string=False,
                    )
                if start_weights_raw is not None:
                    if not isinstance(start_weights_raw, dict) or len(start_weights_raw) == 0:
                        raise ValueError(
                            f"{location}: params.start_weights must be a non-empty object when provided. "
                            "Fix: map each declared state to a numeric weight."
                        )
                    normalized_start_weights: dict[object, float] = {}
                    for raw_key, raw_weight in start_weights_raw.items():
                        state_key = _coerce_state_ref(
                            raw_key,
                            field_name="params.start_weights key",
                            allow_int_string=True,
                        )
                        if state_key in normalized_start_weights:
                            raise ValueError(
                                f"{location}: params.start_weights has duplicate keys after normalization. "
                                "Fix: include one unique key per state."
                            )
                        try:
                            weight = float(raw_weight)
                        except (TypeError, ValueError) as exc:
                            raise ValueError(
                                f"{location}: params.start_weights['{raw_key}'] must be numeric. "
                                "Fix: provide numeric non-negative start weights."
                            ) from exc
                        if weight < 0:
                            raise ValueError(
                                f"{location}: params.start_weights['{raw_key}'] cannot be negative. "
                                "Fix: use non-negative start weights."
                            )
                        normalized_start_weights[state_key] = weight
                    if set(normalized_start_weights.keys()) != state_set:
                        raise ValueError(
                            f"{location}: params.start_weights keys must exactly match params.states. "
                            "Fix: provide one start weight for each state and remove extras."
                        )
                    if not any(weight > 0 for weight in normalized_start_weights.values()):
                        raise ValueError(
                            f"{location}: params.start_weights must include at least one value > 0. "
                            "Fix: set one or more start weights above zero."
                        )

                terminal_states_raw = params.get("terminal_states", [])
                if not isinstance(terminal_states_raw, list):
                    raise ValueError(
                        f"{location}: params.terminal_states must be a list when provided. "
                        "Fix: set params.terminal_states to a list of declared states or omit it."
                    )
                terminal_states: set[object] = set()
                for idx, raw_terminal in enumerate(terminal_states_raw):
                    terminal_state = _coerce_state_ref(
                        raw_terminal,
                        field_name=f"params.terminal_states[{idx}]",
                        allow_int_string=False,
                    )
                    if terminal_state in terminal_states:
                        raise ValueError(
                            f"{location}: params.terminal_states contains duplicate values. "
                            "Fix: list each terminal state only once."
                        )
                    terminal_states.add(terminal_state)

                dwell_min_raw = params.get("dwell_min", 1)
                dwell_max_raw = params.get("dwell_max", dwell_min_raw)
                try:
                    dwell_min = int(dwell_min_raw)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"{location}: params.dwell_min must be an integer. "
                        "Fix: set params.dwell_min to 1 or greater."
                    ) from exc
                try:
                    dwell_max = int(dwell_max_raw)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"{location}: params.dwell_max must be an integer. "
                        "Fix: set params.dwell_max to an integer >= params.dwell_min."
                    ) from exc
                if dwell_min < 1:
                    raise ValueError(
                        f"{location}: params.dwell_min must be >= 1. "
                        "Fix: set params.dwell_min to 1 or greater."
                    )
                if dwell_max < dwell_min:
                    raise ValueError(
                        f"{location}: params.dwell_max cannot be less than params.dwell_min. "
                        "Fix: set params.dwell_max >= params.dwell_min."
                    )

                dwell_by_state_raw = params.get("dwell_by_state")
                if dwell_by_state_raw is not None:
                    if not isinstance(dwell_by_state_raw, dict):
                        raise ValueError(
                            f"{location}: params.dwell_by_state must be an object when provided. "
                            "Fix: set params.dwell_by_state to a state->min/max object map."
                        )
                    seen_dwell_states: set[object] = set()
                    for raw_key, raw_bounds in dwell_by_state_raw.items():
                        dwell_state = _coerce_state_ref(
                            raw_key,
                            field_name="params.dwell_by_state key",
                            allow_int_string=True,
                        )
                        if dwell_state in seen_dwell_states:
                            raise ValueError(
                                f"{location}: params.dwell_by_state has duplicate keys after normalization. "
                                "Fix: include one per-state dwell override entry."
                            )
                        seen_dwell_states.add(dwell_state)
                        if not isinstance(raw_bounds, dict):
                            raise ValueError(
                                f"{location}: params.dwell_by_state['{raw_key}'] must be an object. "
                                "Fix: configure per-state min/max integer bounds."
                            )
                        min_raw = raw_bounds.get("min", dwell_min)
                        max_raw = raw_bounds.get("max", min_raw)
                        try:
                            min_bound = int(min_raw)
                        except (TypeError, ValueError) as exc:
                            raise ValueError(
                                f"{location}: params.dwell_by_state['{raw_key}'].min must be an integer. "
                                "Fix: set per-state min dwell to 1 or greater."
                            ) from exc
                        try:
                            max_bound = int(max_raw)
                        except (TypeError, ValueError) as exc:
                            raise ValueError(
                                f"{location}: params.dwell_by_state['{raw_key}'].max must be an integer. "
                                "Fix: set per-state max dwell to an integer >= min."
                            ) from exc
                        if min_bound < 1:
                            raise ValueError(
                                f"{location}: params.dwell_by_state['{raw_key}'].min must be >= 1. "
                                "Fix: set per-state min dwell to 1 or greater."
                            )
                        if max_bound < min_bound:
                            raise ValueError(
                                f"{location}: params.dwell_by_state['{raw_key}'].max cannot be less than min. "
                                "Fix: set per-state max dwell >= min."
                            )

                transitions_raw = params.get("transitions")
                if not isinstance(transitions_raw, dict) or len(transitions_raw) == 0:
                    raise ValueError(
                        f"{location}: params.transitions must be a non-empty object. "
                        "Fix: set params.transitions like {'new': {'active': 1.0}}."
                    )
                normalized_transitions: dict[object, dict[object, float]] = {}
                for raw_from, raw_targets in transitions_raw.items():
                    from_state = _coerce_state_ref(
                        raw_from,
                        field_name="params.transitions key",
                        allow_int_string=True,
                    )
                    if from_state in normalized_transitions:
                        raise ValueError(
                            f"{location}: params.transitions has duplicate from-state keys after normalization. "
                            "Fix: include one unique from-state entry per declared state."
                        )
                    if not isinstance(raw_targets, dict) or len(raw_targets) == 0:
                        raise ValueError(
                            f"{location}: params.transitions['{raw_from}'] must be a non-empty object. "
                            "Fix: configure one or more outbound transition weights."
                        )
                    normalized_targets: dict[object, float] = {}
                    has_positive_weight = False
                    for raw_to, raw_weight in raw_targets.items():
                        to_state = _coerce_state_ref(
                            raw_to,
                            field_name=f"params.transitions['{raw_from}'] key",
                            allow_int_string=True,
                        )
                        if to_state == from_state:
                            raise ValueError(
                                f"{location}: params.transitions['{raw_from}'] cannot include self-transition '{raw_to}'. "
                                "Fix: remove self-transition edges and use dwell controls for state hold behavior."
                            )
                        if to_state in normalized_targets:
                            raise ValueError(
                                f"{location}: params.transitions['{raw_from}'] has duplicate targets after normalization. "
                                "Fix: include each target state only once."
                            )
                        try:
                            weight = float(raw_weight)
                        except (TypeError, ValueError) as exc:
                            raise ValueError(
                                f"{location}: params.transitions['{raw_from}']['{raw_to}'] must be numeric. "
                                "Fix: use numeric non-negative transition weights."
                            ) from exc
                        if weight < 0:
                            raise ValueError(
                                f"{location}: params.transitions['{raw_from}']['{raw_to}'] cannot be negative. "
                                "Fix: use non-negative transition weights."
                            )
                        if weight > 0:
                            has_positive_weight = True
                        normalized_targets[to_state] = weight
                    if not has_positive_weight:
                        raise ValueError(
                            f"{location}: params.transitions['{raw_from}'] must include at least one value > 0. "
                            "Fix: set one or more outbound transition weights above zero."
                        )
                    normalized_transitions[from_state] = normalized_targets

                for terminal_state in terminal_states:
                    outbound = normalized_transitions.get(terminal_state)
                    if outbound:
                        raise ValueError(
                            f"{location}: terminal state '{terminal_state}' cannot define outbound transitions. "
                            "Fix: remove transition entries for terminal states."
                        )

                for state in states:
                    if state in terminal_states:
                        continue
                    if state not in normalized_transitions:
                        raise ValueError(
                            f"{location}: non-terminal state '{state}' is missing transition weights. "
                            "Fix: add one or more outbound transition targets for every non-terminal state."
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
                resolved_path = resolve_repo_path(path)
                if not resolved_path.exists():
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'sample_csv' params.path '{path}' does not exist. "
                        "Fix: provide an existing CSV file path (for example tests/fixtures/city_country_pool.csv)."
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
                match_col_raw = params.get("match_column")
                if match_col_raw is not None and not isinstance(match_col_raw, str):
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'sample_csv' params.match_column must be a string when provided. "
                        "Fix: set params.match_column to an existing source column name or remove it."
                    )

                match_col: str | None = None
                if isinstance(match_col_raw, str):
                    stripped_match_col = match_col_raw.strip()
                    if stripped_match_col != "":
                        match_col = stripped_match_col

                match_col_idx_raw = params.get("match_column_index")
                if match_col is None:
                    if match_col_idx_raw is not None:
                        raise ValueError(
                            f"Table '{t.table_name}', column '{c.name}': generator 'sample_csv' params.match_column_index requires params.match_column. "
                            "Fix: set params.match_column to an existing source column name or remove params.match_column_index."
                        )
                else:
                    if match_col == c.name:
                        raise ValueError(
                            f"Table '{t.table_name}', column '{c.name}': generator 'sample_csv' cannot reference itself in params.match_column. "
                            "Fix: choose a different source column name."
                        )
                    if match_col not in col_map:
                        raise ValueError(
                            f"Table '{t.table_name}', column '{c.name}': generator 'sample_csv' params.match_column '{match_col}' was not found. "
                            "Fix: use an existing source column name."
                        )
                    depends_on = c.depends_on or []
                    if match_col not in depends_on:
                        raise ValueError(
                            f"Table '{t.table_name}', column '{c.name}': generator 'sample_csv' requires depends_on to include '{match_col}' when params.match_column is set. "
                            "Fix: add the source column to depends_on so it generates first."
                        )
                    if match_col_idx_raw is None:
                        raise ValueError(
                            f"Table '{t.table_name}', column '{c.name}': generator 'sample_csv' requires params.match_column_index when params.match_column is set. "
                            "Fix: set params.match_column_index to the CSV column index that matches params.match_column."
                        )
                    try:
                        match_col_idx = int(match_col_idx_raw)
                    except (TypeError, ValueError) as exc:
                        raise ValueError(
                            f"Table '{t.table_name}', column '{c.name}': generator 'sample_csv' params.match_column_index must be an integer. "
                            "Fix: set params.match_column_index to 0 or greater."
                        ) from exc
                    if match_col_idx < 0:
                        raise ValueError(
                            f"Table '{t.table_name}', column '{c.name}': generator 'sample_csv' params.match_column_index cannot be negative. "
                            "Fix: set params.match_column_index to 0 or greater."
                        )
            if c.generator == "if_then":
                params = c.params or {}
                if_col = params.get("if_column")
                if not isinstance(if_col, str) or if_col.strip() == "":
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'if_then' requires params.if_column. "
                        "Fix: set params.if_column to an existing source column name."
                    )
                if_col = if_col.strip()
                if if_col == c.name:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'if_then' cannot reference itself in params.if_column. "
                        "Fix: choose a different source column name."
                    )
                if if_col not in col_map:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'if_then' params.if_column '{if_col}' was not found. "
                        "Fix: use an existing source column name."
                    )

                depends_on = c.depends_on or []
                if if_col not in depends_on:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'if_then' requires depends_on to include '{if_col}'. "
                        "Fix: add the source column to depends_on so it generates first."
                    )

                op = params.get("operator", "==")
                if not isinstance(op, str) or op not in {"==", "!="}:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'if_then' has unsupported operator '{op}'. "
                        "Fix: use operator '==' or '!='."
                    )
                if "value" not in params:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'if_then' requires params.value. "
                        "Fix: set params.value to a comparison value."
                    )
                if "then_value" not in params or "else_value" not in params:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'if_then' requires params.then_value and params.else_value. "
                        "Fix: set both output values for true/false branches."
                    )
                for key in ("value", "then_value", "else_value"):
                    val = params.get(key)
                    if isinstance(val, (dict, list)):
                        raise ValueError(
                            f"Table '{t.table_name}', column '{c.name}': generator 'if_then' params.{key} must be a scalar value. "
                            "Fix: use string/number/bool/null values for if_then params."
                        )
            if c.generator == "time_offset":
                params = c.params or {}
                if c.dtype not in {"date", "datetime"}:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'time_offset' requires dtype date or datetime. "
                        "Fix: set column dtype to 'date' or 'datetime'."
                    )
                base_col = params.get("base_column")
                if not isinstance(base_col, str) or base_col.strip() == "":
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'time_offset' requires params.base_column. "
                        "Fix: set params.base_column to an existing source date/datetime column name."
                    )
                base_col = base_col.strip()
                if base_col == c.name:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'time_offset' cannot reference itself in params.base_column. "
                        "Fix: choose a different source column name."
                    )
                if base_col not in col_map:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'time_offset' params.base_column '{base_col}' was not found. "
                        "Fix: use an existing source column name."
                    )
                base_dtype = col_map[base_col].dtype
                if base_dtype != c.dtype:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'time_offset' requires source and target dtypes to match (source '{base_dtype}', target '{c.dtype}'). "
                        "Fix: use matching date/date or datetime/datetime columns."
                    )
                depends_on = c.depends_on or []
                if base_col not in depends_on:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'time_offset' requires depends_on to include '{base_col}'. "
                        "Fix: add the source column to depends_on so it generates first."
                    )
                direction = params.get("direction", "after")
                if not isinstance(direction, str) or direction not in {"after", "before"}:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'time_offset' has unsupported direction '{direction}'. "
                        "Fix: use direction 'after' or 'before'."
                    )

                if c.dtype == "date":
                    min_key = "min_days"
                    max_key = "max_days"
                    wrong_min_key = "min_seconds"
                    wrong_max_key = "max_seconds"
                    unit_hint = "day"
                else:
                    min_key = "min_seconds"
                    max_key = "max_seconds"
                    wrong_min_key = "min_days"
                    wrong_max_key = "max_days"
                    unit_hint = "second"

                if wrong_min_key in params or wrong_max_key in params:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'time_offset' has unsupported offset keys for dtype '{c.dtype}'. "
                        f"Fix: use params.{min_key} and params.{max_key} for this dtype."
                    )

                min_raw = params.get(min_key, 0)
                max_raw = params.get(max_key, min_raw)
                try:
                    min_offset = int(min_raw)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'time_offset' params.{min_key} must be an integer. "
                        f"Fix: set params.{min_key} to a whole-number {unit_hint} offset."
                    ) from exc
                try:
                    max_offset = int(max_raw)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'time_offset' params.{max_key} must be an integer. "
                        f"Fix: set params.{max_key} to a whole-number {unit_hint} offset."
                    ) from exc
                if min_offset < 0 or max_offset < 0:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'time_offset' offsets must be non-negative. "
                        "Fix: set min/max offsets to 0 or greater."
                    )
                if min_offset > max_offset:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'time_offset' min offset cannot exceed max offset. "
                        "Fix: set min offset <= max offset."
                    )
            if c.generator == "hierarchical_category":
                params = c.params or {}
                if c.dtype != "text":
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'hierarchical_category' requires dtype text. "
                        "Fix: set column dtype to 'text'."
                    )
                parent_col = params.get("parent_column")
                if not isinstance(parent_col, str) or parent_col.strip() == "":
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'hierarchical_category' requires params.parent_column. "
                        "Fix: set params.parent_column to an existing source category column name."
                    )
                parent_col = parent_col.strip()
                if parent_col == c.name:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'hierarchical_category' cannot reference itself in params.parent_column. "
                        "Fix: choose a different source column name."
                    )
                if parent_col not in col_map:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'hierarchical_category' params.parent_column '{parent_col}' was not found. "
                        "Fix: use an existing source column name."
                    )
                depends_on = c.depends_on or []
                if parent_col not in depends_on:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'hierarchical_category' requires depends_on to include '{parent_col}'. "
                        "Fix: add the source column to depends_on so it generates first."
                    )
                hierarchy = params.get("hierarchy")
                if not isinstance(hierarchy, dict) or not hierarchy:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{c.name}': generator 'hierarchical_category' requires a non-empty params.hierarchy object. "
                        "Fix: set params.hierarchy to a mapping like {'Parent': ['ChildA', 'ChildB']}."
                    )
                for parent_value, children in hierarchy.items():
                    if not isinstance(children, list) or len(children) == 0:
                        raise ValueError(
                            f"Table '{t.table_name}', column '{c.name}': generator 'hierarchical_category' parent '{parent_value}' must map to a non-empty child list. "
                            "Fix: configure one or more child values per parent in params.hierarchy."
                        )
                    for child_value in children:
                        if isinstance(child_value, (dict, list)):
                            raise ValueError(
                                f"Table '{t.table_name}', column '{c.name}': generator 'hierarchical_category' child values must be scalar. "
                                "Fix: use string/number/bool/null values in child lists."
                            )
                default_children = params.get("default_children")
                if default_children is not None:
                    if not isinstance(default_children, list) or len(default_children) == 0:
                        raise ValueError(
                            f"Table '{t.table_name}', column '{c.name}': generator 'hierarchical_category' params.default_children must be a non-empty list when provided. "
                            "Fix: set params.default_children to one or more fallback child values or omit it."
                        )
                    for child_value in default_children:
                        if isinstance(child_value, (dict, list)):
                            raise ValueError(
                                f"Table '{t.table_name}', column '{c.name}': generator 'hierarchical_category' params.default_children values must be scalar. "
                                "Fix: use string/number/bool/null values in params.default_children."
                            )
                parent_choices = col_map[parent_col].choices or []
                if parent_choices and default_children is None:
                    missing = [
                        choice
                        for choice in parent_choices
                        if choice not in hierarchy and str(choice) not in hierarchy
                    ]
                    if missing:
                        missing_display = ", ".join(str(x) for x in missing)
                        raise ValueError(
                            f"Table '{t.table_name}', column '{c.name}': generator 'hierarchical_category' is missing hierarchy entries for parent choices ({missing_display}). "
                            "Fix: add those choices to params.hierarchy or set params.default_children."
                        )
        incoming = [fk for fk in project.foreign_keys if fk.child_table == t.table_name]
        incoming_fk_cols = {fk.child_column for fk in incoming}
        _validate_correlation_groups_for_table(
            t,
            col_map=col_map,
            incoming_fk_cols=incoming_fk_cols,
        )

        business_key = t.business_key
        business_key_unique_count = t.business_key_unique_count
        if business_key_unique_count is not None:
            if isinstance(business_key_unique_count, bool) or not isinstance(business_key_unique_count, int):
                raise ValueError(
                    f"Table '{t.table_name}': business_key_unique_count must be an integer when provided. "
                    "Fix: set business_key_unique_count to a positive whole number or omit it."
                )
            if business_key_unique_count <= 0:
                raise ValueError(
                    f"Table '{t.table_name}': business_key_unique_count must be > 0. "
                    "Fix: set business_key_unique_count to a positive whole number."
                )
            if not business_key:
                raise ValueError(
                    f"Table '{t.table_name}': business_key_unique_count requires business_key. "
                    "Fix: configure business_key columns before setting business_key_unique_count."
                )
            if t.row_count > 0 and business_key_unique_count > t.row_count:
                raise ValueError(
                    f"Table '{t.table_name}': business_key_unique_count={business_key_unique_count} cannot exceed row_count={t.row_count}. "
                    "Fix: set business_key_unique_count <= row_count, or increase row_count."
                )
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
                if c.dtype in {"bool", "bytes"}:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{name}': dtype '{c.dtype}' is not supported for business_key. "
                        "Fix: use a stable business identifier column with dtype int/text/decimal/date/datetime."
                    )
                if name in incoming_fk_cols:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{name}': business_key cannot use incoming FK child column. "
                        "Fix: choose non-FK columns for business_key on child tables."
                    )

        business_key_static_columns = t.business_key_static_columns
        if business_key_static_columns is not None:
            if len(business_key_static_columns) == 0:
                raise ValueError(
                    f"Table '{t.table_name}': business_key_static_columns cannot be empty. "
                    "Fix: provide one or more existing column names or omit business_key_static_columns."
                )
            if len(set(business_key_static_columns)) != len(business_key_static_columns):
                raise ValueError(
                    f"Table '{t.table_name}': business_key_static_columns contains duplicate column names. "
                    "Fix: list each static column only once."
                )
            for name in business_key_static_columns:
                if name not in col_map:
                    raise ValueError(
                        f"Table '{t.table_name}': business_key_static_columns includes unknown column '{name}'. "
                        "Fix: use existing column names in business_key_static_columns."
                    )

        business_key_changing_columns = t.business_key_changing_columns
        if business_key_changing_columns is not None:
            if len(business_key_changing_columns) == 0:
                raise ValueError(
                    f"Table '{t.table_name}': business_key_changing_columns cannot be empty. "
                    "Fix: provide one or more existing column names or omit business_key_changing_columns."
                )
            if len(set(business_key_changing_columns)) != len(business_key_changing_columns):
                raise ValueError(
                    f"Table '{t.table_name}': business_key_changing_columns contains duplicate column names. "
                    "Fix: list each changing column only once."
                )
            for name in business_key_changing_columns:
                if name not in col_map:
                    raise ValueError(
                        f"Table '{t.table_name}': business_key_changing_columns includes unknown column '{name}'. "
                        "Fix: use existing column names in business_key_changing_columns."
                    )
                if business_key and name in business_key:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{name}': business_key columns cannot be in business_key_changing_columns. "
                        "Fix: keep business_key columns stable and choose non-business-key changing columns."
                    )

        if business_key_static_columns and business_key_changing_columns:
            overlap = sorted(set(business_key_static_columns) & set(business_key_changing_columns))
            if overlap:
                overlap_display = ", ".join(overlap)
                raise ValueError(
                    f"Table '{t.table_name}': business_key_static_columns and business_key_changing_columns overlap ({overlap_display}). "
                    "Fix: put each column in only one business-key behavior list."
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
                t.business_key_static_columns is not None,
                t.business_key_changing_columns is not None,
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
            if business_key_changing_columns and t.scd_tracked_columns:
                if set(business_key_changing_columns) != set(t.scd_tracked_columns):
                    raise ValueError(
                        f"Table '{t.table_name}': business_key_changing_columns must match scd_tracked_columns when both are provided. "
                        "Fix: use the same column set in both fields, or leave scd_tracked_columns empty."
                    )
            tracked = business_key_changing_columns or t.scd_tracked_columns or []
            if len(tracked) == 0:
                raise ValueError(
                    f"Table '{t.table_name}': scd_mode='{scd_mode}' requires non-empty business_key_changing_columns or scd_tracked_columns. "
                    "Fix: provide one or more existing column names for changing attributes."
                )
            for name in tracked:
                if name not in col_map:
                    raise ValueError(
                        f"Table '{t.table_name}': changing columns include unknown column '{name}'. "
                        "Fix: use existing column names in business_key_changing_columns or scd_tracked_columns."
                    )
                if business_key and name in business_key:
                    raise ValueError(
                        f"Table '{t.table_name}', column '{name}': business_key columns cannot be tracked as changing. "
                        "Fix: track non-business-key columns for SCD changes."
                    )

            if scd_mode == "scd1" and business_key_unique_count is not None and t.row_count > 0:
                if business_key_unique_count != t.row_count:
                    raise ValueError(
                        f"Table '{t.table_name}': scd_mode='scd1' requires one row per business key, so business_key_unique_count ({business_key_unique_count}) must equal row_count ({t.row_count}). "
                        "Fix: set business_key_unique_count equal to row_count for SCD1 tables."
                    )

            if scd_mode == "scd2":
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

    timeline_constraints = project.timeline_constraints
    if timeline_constraints is not None:
        if not isinstance(timeline_constraints, list):
            raise ValueError(
                _validation_error(
                    "Project",
                    "timeline_constraints must be a list when provided",
                    "set timeline_constraints to a list of rule objects or omit timeline_constraints",
                )
            )
        if len(timeline_constraints) == 0:
            raise ValueError(
                _validation_error(
                    "Project",
                    "timeline_constraints cannot be empty when provided",
                    "add one or more timeline constraint rules or omit timeline_constraints",
                )
            )

        seen_rule_ids: set[str] = set()
        seen_targets: set[tuple[str, str]] = set()

        for rule_index, raw_rule in enumerate(timeline_constraints):
            location = f"Project timeline_constraints[{rule_index}]"
            if not isinstance(raw_rule, dict):
                raise ValueError(
                    _validation_error(
                        location,
                        "rule must be a JSON object",
                        "configure this timeline rule as an object with rule_id, child_table, child_column, and references",
                    )
                )

            rule_id_raw = raw_rule.get("rule_id")
            if not isinstance(rule_id_raw, str) or rule_id_raw.strip() == "":
                raise ValueError(
                    _validation_error(
                        location,
                        "rule_id is required",
                        "set rule_id to a non-empty string",
                    )
                )
            rule_id = rule_id_raw.strip()
            if rule_id in seen_rule_ids:
                raise ValueError(
                    _validation_error(
                        "Project",
                        f"duplicate timeline rule_id '{rule_id}'",
                        "use unique rule_id values in timeline_constraints",
                    )
                )
            seen_rule_ids.add(rule_id)

            mode_raw = raw_rule.get("mode", "enforce")
            if not isinstance(mode_raw, str) or mode_raw.strip() == "":
                raise ValueError(
                    _validation_error(
                        location,
                        "mode must be a string when provided",
                        "set mode to 'enforce' or omit mode",
                    )
                )
            mode = mode_raw.strip().lower()
            if mode != "enforce":
                raise ValueError(
                    _validation_error(
                        location,
                        f"unsupported mode '{mode_raw}'",
                        "set mode to 'enforce' for this release",
                    )
                )

            child_table_raw = raw_rule.get("child_table")
            if not isinstance(child_table_raw, str) or child_table_raw.strip() == "":
                raise ValueError(
                    _validation_error(
                        location,
                        "child_table is required",
                        "set child_table to an existing table name",
                    )
                )
            child_table_name = child_table_raw.strip()
            child_table = table_map.get(child_table_name)
            if child_table is None:
                raise ValueError(
                    _validation_error(
                        location,
                        f"child_table '{child_table_name}' was not found",
                        "use an existing table name for child_table",
                    )
                )

            child_column_raw = raw_rule.get("child_column")
            if not isinstance(child_column_raw, str) or child_column_raw.strip() == "":
                raise ValueError(
                    _validation_error(
                        location,
                        "child_column is required",
                        "set child_column to an existing date/datetime column in child_table",
                    )
                )
            child_column_name = child_column_raw.strip()
            child_cols = {column.name: column for column in child_table.columns}
            child_column = child_cols.get(child_column_name)
            if child_column is None:
                raise ValueError(
                    _validation_error(
                        location,
                        f"child_column '{child_column_name}' was not found on table '{child_table_name}'",
                        "use an existing child table column name",
                    )
                )
            if child_column.dtype not in {"date", "datetime"}:
                raise ValueError(
                    _validation_error(
                        location,
                        f"child_column '{child_column_name}' must be dtype date or datetime",
                        "choose a date/datetime child column for timeline constraints",
                    )
                )

            target = (child_table_name, child_column_name)
            if target in seen_targets:
                raise ValueError(
                    _validation_error(
                        "Project",
                        f"multiple timeline rules target '{child_table_name}.{child_column_name}'",
                        "define at most one timeline rule per child_table + child_column",
                    )
                )
            seen_targets.add(target)

            references_raw = raw_rule.get("references")
            if not isinstance(references_raw, list) or len(references_raw) == 0:
                raise ValueError(
                    _validation_error(
                        location,
                        "references must be a non-empty list",
                        "configure one or more parent reference objects",
                    )
                )

            child_dtype = child_column.dtype
            for reference_index, raw_reference in enumerate(references_raw):
                ref_location = f"{location}, references[{reference_index}]"
                if not isinstance(raw_reference, dict):
                    raise ValueError(
                        _validation_error(
                            ref_location,
                            "reference must be a JSON object",
                            "configure parent_table, parent_column, via_child_fk, direction, and offset bounds",
                        )
                    )

                parent_table_raw = raw_reference.get("parent_table")
                if not isinstance(parent_table_raw, str) or parent_table_raw.strip() == "":
                    raise ValueError(
                        _validation_error(
                            ref_location,
                            "parent_table is required",
                            "set parent_table to an existing parent table name",
                        )
                    )
                parent_table_name = parent_table_raw.strip()
                parent_table = table_map.get(parent_table_name)
                if parent_table is None:
                    raise ValueError(
                        _validation_error(
                            ref_location,
                            f"parent_table '{parent_table_name}' was not found",
                            "use an existing table name for parent_table",
                        )
                    )

                parent_column_raw = raw_reference.get("parent_column")
                if not isinstance(parent_column_raw, str) or parent_column_raw.strip() == "":
                    raise ValueError(
                        _validation_error(
                            ref_location,
                            "parent_column is required",
                            "set parent_column to an existing date/datetime column in parent_table",
                        )
                    )
                parent_column_name = parent_column_raw.strip()
                parent_cols = {column.name: column for column in parent_table.columns}
                parent_column = parent_cols.get(parent_column_name)
                if parent_column is None:
                    raise ValueError(
                        _validation_error(
                            ref_location,
                            f"parent_column '{parent_column_name}' was not found on table '{parent_table_name}'",
                            "use an existing parent table column name",
                        )
                    )
                if parent_column.dtype not in {"date", "datetime"}:
                    raise ValueError(
                        _validation_error(
                            ref_location,
                            f"parent_column '{parent_column_name}' must be dtype date or datetime",
                            "choose a date/datetime parent column for timeline constraints",
                        )
                    )
                if parent_column.dtype != child_dtype:
                    raise ValueError(
                        _validation_error(
                            ref_location,
                            f"parent_column '{parent_table_name}.{parent_column_name}' dtype must match child_column '{child_table_name}.{child_column_name}'",
                            "use date->date or datetime->datetime references",
                        )
                    )

                via_child_fk_raw = raw_reference.get("via_child_fk")
                if not isinstance(via_child_fk_raw, str) or via_child_fk_raw.strip() == "":
                    raise ValueError(
                        _validation_error(
                            ref_location,
                            "via_child_fk is required",
                            "set via_child_fk to the child FK column used to resolve the parent row",
                        )
                    )
                via_child_fk = via_child_fk_raw.strip()
                if via_child_fk not in child_cols:
                    raise ValueError(
                        _validation_error(
                            ref_location,
                            f"via_child_fk '{via_child_fk}' was not found on table '{child_table_name}'",
                            "use an existing child FK column name",
                        )
                    )

                direct_fk = next(
                    (
                        fk
                        for fk in project.foreign_keys
                        if fk.child_table == child_table_name
                        and fk.child_column == via_child_fk
                        and fk.parent_table == parent_table_name
                    ),
                    None,
                )
                if direct_fk is None:
                    raise ValueError(
                        _validation_error(
                            ref_location,
                            (
                                f"via_child_fk '{child_table_name}.{via_child_fk}' does not directly reference "
                                f"parent_table '{parent_table_name}'"
                            ),
                            "define a direct FK from child_table.via_child_fk to parent_table before using this reference",
                        )
                    )

                direction_raw = raw_reference.get("direction")
                if not isinstance(direction_raw, str) or direction_raw.strip() == "":
                    raise ValueError(
                        _validation_error(
                            ref_location,
                            "direction is required",
                            "set direction to 'after' or 'before'",
                        )
                    )
                direction = direction_raw.strip().lower()
                if direction not in {"after", "before"}:
                    raise ValueError(
                        _validation_error(
                            ref_location,
                            f"unsupported direction '{direction_raw}'",
                            "set direction to 'after' or 'before'",
                        )
                    )

                if child_dtype == "date":
                    min_days = _parse_non_negative_int(
                        raw_reference.get("min_days", 0),
                        location=ref_location,
                        field_name="min_days",
                        hint="set min_days to an integer >= 0",
                    )
                    max_days = _parse_non_negative_int(
                        raw_reference.get("max_days", min_days),
                        location=ref_location,
                        field_name="max_days",
                        hint="set max_days to an integer >= min_days",
                    )
                    if max_days < min_days:
                        raise ValueError(
                            _validation_error(
                                ref_location,
                                "max_days cannot be less than min_days",
                                "set max_days >= min_days",
                            )
                        )
                    if "min_seconds" in raw_reference or "max_seconds" in raw_reference:
                        raise ValueError(
                            _validation_error(
                                ref_location,
                                "date references cannot use min_seconds/max_seconds",
                                "use min_days/max_days for date child/parent columns",
                            )
                        )
                else:
                    min_seconds = _parse_non_negative_int(
                        raw_reference.get("min_seconds", 0),
                        location=ref_location,
                        field_name="min_seconds",
                        hint="set min_seconds to an integer >= 0",
                    )
                    max_seconds = _parse_non_negative_int(
                        raw_reference.get("max_seconds", min_seconds),
                        location=ref_location,
                        field_name="max_seconds",
                        hint="set max_seconds to an integer >= min_seconds",
                    )
                    if max_seconds < min_seconds:
                        raise ValueError(
                            _validation_error(
                                ref_location,
                                "max_seconds cannot be less than min_seconds",
                                "set max_seconds >= min_seconds",
                            )
                        )
                    if "min_days" in raw_reference or "max_days" in raw_reference:
                        raise ValueError(
                            _validation_error(
                                ref_location,
                                "datetime references cannot use min_days/max_days",
                                "use min_seconds/max_seconds for datetime child/parent columns",
                            )
                        )

