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


def _validation_error(location: str, issue: str, hint: str) -> str:
    return f"{location}: {issue}. Fix: {hint}."


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

