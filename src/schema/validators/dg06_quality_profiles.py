from __future__ import annotations

import math

from src.schema.types import SchemaProject
from src.schema.types import TableSpec
from src.schema.validators.common import _is_scalar_json_value
from src.schema.validators.common import _parse_non_negative_finite_float
from src.schema.validators.common import _parse_non_negative_int
from src.schema.validators.common import _parse_probability
from src.schema.validators.common import _validation_error


def validate_data_quality_profiles(project: SchemaProject, *, table_map: dict[str, TableSpec]) -> None:
    data_quality_profiles = project.data_quality_profiles
    if data_quality_profiles is not None:
        if not isinstance(data_quality_profiles, list):
            raise ValueError(
                _validation_error(
                    "Project",
                    "data_quality_profiles must be a list when provided",
                    "set data_quality_profiles to a list of profile objects or omit data_quality_profiles",
                )
            )
        if len(data_quality_profiles) == 0:
            raise ValueError(
                _validation_error(
                    "Project",
                    "data_quality_profiles cannot be empty when provided",
                    "add one or more DG06 profiles or omit data_quality_profiles",
                )
            )

        seen_profile_ids: set[str] = set()
        for profile_index, raw_profile in enumerate(data_quality_profiles):
            location = f"Project data_quality_profiles[{profile_index}]"
            if not isinstance(raw_profile, dict):
                raise ValueError(
                    _validation_error(
                        location,
                        "profile must be a JSON object",
                        "configure this DG06 profile as an object with profile_id, table, column, and rule fields",
                    )
                )

            profile_id_raw = raw_profile.get("profile_id")
            if not isinstance(profile_id_raw, str) or profile_id_raw.strip() == "":
                raise ValueError(
                    _validation_error(
                        location,
                        "profile_id is required",
                        "set profile_id to a non-empty string",
                    )
                )
            profile_id = profile_id_raw.strip()
            if profile_id in seen_profile_ids:
                raise ValueError(
                    _validation_error(
                        "Project",
                        f"duplicate DG06 profile_id '{profile_id}'",
                        "use unique profile_id values in data_quality_profiles",
                    )
                )
            seen_profile_ids.add(profile_id)

            table_raw = raw_profile.get("table")
            if not isinstance(table_raw, str) or table_raw.strip() == "":
                raise ValueError(
                    _validation_error(
                        location,
                        "table is required",
                        "set table to an existing table name",
                    )
                )
            table_name = table_raw.strip()
            table = table_map.get(table_name)
            if table is None:
                raise ValueError(
                    _validation_error(
                        location,
                        f"table '{table_name}' was not found",
                        "use an existing table name for DG06 profiles",
                    )
                )
            table_cols = {column.name: column for column in table.columns}

            column_raw = raw_profile.get("column")
            if not isinstance(column_raw, str) or column_raw.strip() == "":
                raise ValueError(
                    _validation_error(
                        location,
                        "column is required",
                        "set column to an existing target column name on the configured table",
                    )
                )
            column_name = column_raw.strip()
            column = table_cols.get(column_name)
            if column is None:
                raise ValueError(
                    _validation_error(
                        location,
                        f"column '{column_name}' was not found on table '{table_name}'",
                        "use an existing column name for DG06 profiles",
                    )
                )
            if column.primary_key:
                raise ValueError(
                    _validation_error(
                        location,
                        f"column '{column_name}' cannot target a primary key",
                        "target a non-primary-key column for DG06 missingness/data-quality profiles",
                    )
                )

            where_raw = raw_profile.get("where")
            if where_raw is not None:
                if not isinstance(where_raw, dict) or len(where_raw) == 0:
                    raise ValueError(
                        _validation_error(
                            location,
                            "where must be a non-empty object when provided",
                            "set where to an object like {\"segment\": [\"VIP\", \"STD\"]} or remove where",
                        )
                    )
                for where_key_raw, where_values_raw in where_raw.items():
                    if not isinstance(where_key_raw, str) or where_key_raw.strip() == "":
                        raise ValueError(
                            _validation_error(
                                location,
                                "where contains an empty or non-string column key",
                                "use existing column-name string keys in where",
                            )
                        )
                    where_column = where_key_raw.strip()
                    if where_column not in table_cols:
                        raise ValueError(
                            _validation_error(
                                location,
                                f"where column '{where_column}' was not found on table '{table_name}'",
                                "use existing table columns in where predicates",
                            )
                        )
                    if isinstance(where_values_raw, list):
                        if len(where_values_raw) == 0:
                            raise ValueError(
                                _validation_error(
                                    location,
                                    f"where['{where_key_raw}'] cannot be an empty list",
                                    "provide one or more scalar match values in where lists",
                                )
                            )
                        match_values = where_values_raw
                    else:
                        match_values = [where_values_raw]
                    for match_value in match_values:
                        if not _is_scalar_json_value(match_value):
                            raise ValueError(
                                _validation_error(
                                    location,
                                    f"where['{where_key_raw}'] values must be scalar",
                                    "use scalar string/number/bool/null values in where predicates",
                                )
                            )

            kind_raw = raw_profile.get("kind")
            if not isinstance(kind_raw, str) or kind_raw.strip() == "":
                raise ValueError(
                    _validation_error(
                        location,
                        "kind is required",
                        "set kind to 'missingness' or 'quality_issue'",
                    )
                )
            kind = kind_raw.strip().lower()
            if kind not in {"missingness", "quality_issue"}:
                raise ValueError(
                    _validation_error(
                        location,
                        f"unsupported kind '{kind_raw}'",
                        "set kind to 'missingness' or 'quality_issue'",
                    )
                )

            if kind == "missingness":
                mechanism_raw = raw_profile.get("mechanism")
                if not isinstance(mechanism_raw, str) or mechanism_raw.strip() == "":
                    raise ValueError(
                        _validation_error(
                            location,
                            "missingness.mechanism is required",
                            "set mechanism to 'mcar', 'mar', or 'mnar'",
                        )
                    )
                mechanism = mechanism_raw.strip().lower()
                if mechanism not in {"mcar", "mar", "mnar"}:
                    raise ValueError(
                        _validation_error(
                            location,
                            f"unsupported missingness mechanism '{mechanism_raw}'",
                            "set mechanism to 'mcar', 'mar', or 'mnar'",
                        )
                    )
                _parse_probability(
                    raw_profile.get("base_rate"),
                    location=location,
                    field_name="base_rate",
                    hint="set base_rate to a numeric value between 0 and 1",
                )

                driver_column_raw = raw_profile.get("driver_column")
                if mechanism == "mcar":
                    if driver_column_raw is not None:
                        raise ValueError(
                            _validation_error(
                                location,
                                "driver_column is not used for mechanism 'mcar'",
                                "remove driver_column or switch mechanism to 'mar'/'mnar'",
                            )
                        )
                elif mechanism == "mar":
                    if not isinstance(driver_column_raw, str) or driver_column_raw.strip() == "":
                        raise ValueError(
                            _validation_error(
                                location,
                                "driver_column is required for mechanism 'mar'",
                                "set driver_column to an existing source column on the same table",
                            )
                        )
                    driver_column = driver_column_raw.strip()
                    if driver_column == column_name:
                        raise ValueError(
                            _validation_error(
                                location,
                                "driver_column cannot equal the target column for mechanism 'mar'",
                                "use another source column for MAR, or set mechanism='mnar' for self-value missingness",
                            )
                        )
                    if driver_column not in table_cols:
                        raise ValueError(
                            _validation_error(
                                location,
                                f"driver_column '{driver_column}' was not found on table '{table_name}'",
                                "use an existing table column for driver_column",
                            )
                        )
                else:
                    if (
                        isinstance(driver_column_raw, str)
                        and driver_column_raw.strip() != ""
                        and driver_column_raw.strip() != column_name
                    ):
                        raise ValueError(
                            _validation_error(
                                location,
                                "driver_column must match the target column for mechanism 'mnar'",
                                "omit driver_column for MNAR or set it to the same target column name",
                            )
                        )

                weights_raw = raw_profile.get("value_weights")
                normalized_weights: dict[str, float] = {}
                if weights_raw is not None:
                    if not isinstance(weights_raw, dict):
                        raise ValueError(
                            _validation_error(
                                location,
                                "value_weights must be an object when provided",
                                "set value_weights to a mapping of source values to non-negative weights",
                            )
                        )
                    for raw_key, raw_weight in weights_raw.items():
                        if not isinstance(raw_key, str) or raw_key.strip() == "":
                            raise ValueError(
                                _validation_error(
                                    location,
                                    "value_weights contains an empty or non-string key",
                                    "use non-empty string keys in value_weights",
                                )
                            )
                        key = raw_key.strip()
                        if key in normalized_weights:
                            raise ValueError(
                                _validation_error(
                                    location,
                                    f"value_weights has duplicate key '{key}' after normalization",
                                    "use unique string keys in value_weights",
                                )
                            )
                        normalized_weights[key] = _parse_non_negative_finite_float(
                            raw_weight,
                            location=location,
                            field_name=f"value_weights['{raw_key}']",
                            hint="use non-negative finite numeric weights",
                        )
                default_weight = _parse_non_negative_finite_float(
                    raw_profile.get("default_weight", 1.0),
                    location=location,
                    field_name="default_weight",
                    hint="set default_weight to a non-negative finite numeric value",
                )
                if mechanism in {"mar", "mnar"}:
                    if default_weight <= 0 and not any(weight > 0 for weight in normalized_weights.values()):
                        raise ValueError(
                            _validation_error(
                                location,
                                "missingness profile provides no positive effective weight",
                                "set at least one value_weights entry > 0 or set default_weight > 0",
                            )
                        )
            else:
                issue_type_raw = raw_profile.get("issue_type")
                if not isinstance(issue_type_raw, str) or issue_type_raw.strip() == "":
                    raise ValueError(
                        _validation_error(
                            location,
                            "quality_issue.issue_type is required",
                            "set issue_type to 'format_error', 'stale_value', or 'drift'",
                        )
                    )
                issue_type = issue_type_raw.strip().lower()
                if issue_type not in {"format_error", "stale_value", "drift"}:
                    raise ValueError(
                        _validation_error(
                            location,
                            f"unsupported issue_type '{issue_type_raw}'",
                            "set issue_type to 'format_error', 'stale_value', or 'drift'",
                        )
                    )
                _parse_probability(
                    raw_profile.get("rate"),
                    location=location,
                    field_name="rate",
                    hint="set rate to a numeric value between 0 and 1",
                )

                if issue_type == "format_error":
                    if column.dtype == "bytes":
                        raise ValueError(
                            _validation_error(
                                location,
                                "format_error does not support dtype bytes",
                                "target a non-bytes column for format_error profiles",
                            )
                        )
                    replacement_raw = raw_profile.get("replacement")
                    if replacement_raw is not None:
                        if not isinstance(replacement_raw, str) or replacement_raw.strip() == "":
                            raise ValueError(
                                _validation_error(
                                    location,
                                    "replacement must be a non-empty string when provided",
                                    "set replacement to a non-empty text token or remove replacement",
                                )
                            )
                elif issue_type == "stale_value":
                    lag_rows = _parse_non_negative_int(
                        raw_profile.get("lag_rows", 1),
                        location=location,
                        field_name="lag_rows",
                        hint="set lag_rows to an integer >= 1",
                    )
                    if lag_rows < 1:
                        raise ValueError(
                            _validation_error(
                                location,
                                "lag_rows must be >= 1",
                                "set lag_rows to 1 or greater for stale_value profiles",
                            )
                        )
                else:
                    if column.dtype not in {"int", "float", "decimal", "date", "datetime"}:
                        raise ValueError(
                            _validation_error(
                                location,
                                f"drift does not support dtype '{column.dtype}'",
                                "use drift on int/float/decimal/date/datetime columns",
                            )
                        )
                    step_raw = raw_profile.get("step")
                    if step_raw is None:
                        raise ValueError(
                            _validation_error(
                                location,
                                "drift.step is required",
                                "set step to a non-zero numeric value (or integer units for date/datetime)",
                            )
                        )
                    if column.dtype in {"date", "datetime"}:
                        if isinstance(step_raw, bool):
                            raise ValueError(
                                _validation_error(
                                    location,
                                    "drift.step must be an integer for date/datetime drift",
                                    "set step to a non-zero integer number of days/seconds",
                                )
                            )
                        try:
                            step = int(step_raw)
                        except (TypeError, ValueError) as exc:
                            raise ValueError(
                                _validation_error(
                                    location,
                                    "drift.step must be an integer for date/datetime drift",
                                    "set step to a non-zero integer number of days/seconds",
                                )
                            ) from exc
                        if step == 0:
                            raise ValueError(
                                _validation_error(
                                    location,
                                    "drift.step cannot be zero",
                                    "set step to a non-zero integer number of days/seconds",
                                )
                            )
                    else:
                        if isinstance(step_raw, bool):
                            raise ValueError(
                                _validation_error(
                                    location,
                                    "drift.step must be numeric",
                                    "set step to a non-zero numeric drift increment",
                                )
                            )
                        try:
                            step = float(step_raw)
                        except (TypeError, ValueError) as exc:
                            raise ValueError(
                                _validation_error(
                                    location,
                                    "drift.step must be numeric",
                                    "set step to a non-zero numeric drift increment",
                                )
                            ) from exc
                        if (not math.isfinite(step)) or step == 0.0:
                            raise ValueError(
                                _validation_error(
                                    location,
                                    "drift.step must be a non-zero finite numeric value",
                                    "set step to a non-zero numeric drift increment",
                                )
                            )

                    start_index = _parse_non_negative_int(
                        raw_profile.get("start_index", 1),
                        location=location,
                        field_name="start_index",
                        hint="set start_index to an integer >= 1",
                    )
                    if start_index < 1:
                        raise ValueError(
                            _validation_error(
                                location,
                                "start_index must be >= 1",
                                "set start_index to 1 or greater for drift profiles",
                            )
                        )



__all__ = ["validate_data_quality_profiles"]
