"""Data-quality profile (DG06) compile helpers."""

from __future__ import annotations

import math

from src.generation.common import _runtime_error
from src.generation.quality_profiles_helpers import _profile_scalar_identity
from src.schema_project_model import SchemaProject


def _compile_data_quality_profiles(project: SchemaProject) -> dict[str, list[dict[str, object]]]:
    raw_profiles = project.data_quality_profiles
    if not raw_profiles:
        return {}

    table_map = {table.table_name: table for table in project.tables}

    def _parse_probability(
        value: object,
        *,
        location: str,
        field_name: str,
        hint: str,
    ) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _runtime_error(
                    location,
                    f"{field_name} must be numeric",
                    hint,
                )
            ) from exc
        if (not math.isfinite(parsed)) or parsed < 0.0 or parsed > 1.0:
            raise ValueError(
                _runtime_error(
                    location,
                    f"{field_name} must be between 0 and 1",
                    hint,
                )
            )
        return parsed

    def _parse_non_negative_float(
        value: object,
        *,
        location: str,
        field_name: str,
        hint: str,
    ) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _runtime_error(
                    location,
                    f"{field_name} must be numeric",
                    hint,
                )
            ) from exc
        if (not math.isfinite(parsed)) or parsed < 0.0:
            raise ValueError(
                _runtime_error(
                    location,
                    f"{field_name} must be a finite value >= 0",
                    hint,
                )
            )
        return parsed

    def _parse_int(
        value: object,
        *,
        location: str,
        field_name: str,
        hint: str,
    ) -> int:
        if isinstance(value, bool):
            raise ValueError(
                _runtime_error(
                    location,
                    f"{field_name} must be an integer",
                    hint,
                )
            )
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _runtime_error(
                    location,
                    f"{field_name} must be an integer",
                    hint,
                )
            ) from exc

    compiled: dict[str, list[dict[str, object]]] = {}
    for profile_index, raw_profile in enumerate(raw_profiles):
        location = f"Project data_quality_profiles[{profile_index}]"
        if not isinstance(raw_profile, dict):
            raise ValueError(
                _runtime_error(
                    location,
                    "profile must be an object",
                    "set each data_quality_profiles item to a JSON object",
                )
            )

        profile_id_raw = raw_profile.get("profile_id")
        if isinstance(profile_id_raw, str) and profile_id_raw.strip() != "":
            profile_id = profile_id_raw.strip()
        else:
            profile_id = f"profile_{profile_index + 1}"

        table_name = str(raw_profile.get("table", "")).strip()
        if table_name == "":
            raise ValueError(
                _runtime_error(
                    location,
                    "table is required",
                    "set table to an existing table name",
                )
            )
        table = table_map.get(table_name)
        if table is None:
            raise ValueError(
                _runtime_error(
                    location,
                    f"table '{table_name}' was not found",
                    "use an existing table name for this DG06 profile",
                )
            )
        table_cols = {column.name: column for column in table.columns}

        column_name = str(raw_profile.get("column", "")).strip()
        if column_name == "":
            raise ValueError(
                _runtime_error(
                    location,
                    "column is required",
                    "set column to an existing target column name",
                )
            )
        column = table_cols.get(column_name)
        if column is None:
            raise ValueError(
                _runtime_error(
                    location,
                    f"column '{column_name}' was not found on table '{table_name}'",
                    "use an existing table column for this DG06 profile",
                )
            )

        where_predicates: list[tuple[str, set[tuple[str, str]]]] = []
        where_raw = raw_profile.get("where")
        if where_raw is not None:
            if not isinstance(where_raw, dict):
                raise ValueError(
                    _runtime_error(
                        location,
                        "where must be an object when provided",
                        "set where to an object mapping columns to scalar value(s) or remove where",
                    )
                )
            for where_key_raw, where_values_raw in where_raw.items():
                if not isinstance(where_key_raw, str) or where_key_raw.strip() == "":
                    raise ValueError(
                        _runtime_error(
                            location,
                            "where contains an empty or non-string column key",
                            "use non-empty table column names as where keys",
                        )
                    )
                where_column = where_key_raw.strip()
                if where_column not in table_cols:
                    raise ValueError(
                        _runtime_error(
                            location,
                            f"where column '{where_column}' was not found on table '{table_name}'",
                            "use existing table columns in where predicates",
                        )
                    )
                if isinstance(where_values_raw, list):
                    if len(where_values_raw) == 0:
                        raise ValueError(
                            _runtime_error(
                                location,
                                f"where['{where_key_raw}'] cannot be an empty list",
                                "provide one or more scalar values in each where list",
                            )
                        )
                    match_values = where_values_raw
                else:
                    match_values = [where_values_raw]
                allowed = {_profile_scalar_identity(value) for value in match_values}
                where_predicates.append((where_column, allowed))

        kind = str(raw_profile.get("kind", "")).strip().lower()
        if kind == "missingness":
            mechanism = str(raw_profile.get("mechanism", "")).strip().lower()
            base_rate = _parse_probability(
                raw_profile.get("base_rate"),
                location=location,
                field_name="base_rate",
                hint="set base_rate to a numeric value between 0 and 1",
            )

            driver_column: str | None = None
            if mechanism == "mcar":
                driver_column = None
            elif mechanism == "mar":
                driver_column = str(raw_profile.get("driver_column", "")).strip()
                if driver_column == "":
                    raise ValueError(
                        _runtime_error(
                            location,
                            "driver_column is required for mechanism 'mar'",
                            "set driver_column to an existing source column name",
                        )
                    )
                if driver_column not in table_cols:
                    raise ValueError(
                        _runtime_error(
                            location,
                            f"driver_column '{driver_column}' was not found on table '{table_name}'",
                            "use an existing table column for driver_column",
                        )
                    )
            elif mechanism == "mnar":
                driver_column = column_name
            else:
                raise ValueError(
                    _runtime_error(
                        location,
                        f"unsupported missingness mechanism '{mechanism}'",
                        "set mechanism to 'mcar', 'mar', or 'mnar'",
                    )
                )

            weights_raw = raw_profile.get("value_weights", {})
            if not isinstance(weights_raw, dict):
                raise ValueError(
                    _runtime_error(
                        location,
                        "value_weights must be an object when provided",
                        "set value_weights to a mapping of source values to non-negative weights",
                    )
                )
            normalized_weights: dict[str, float] = {}
            for raw_key, raw_weight in weights_raw.items():
                if not isinstance(raw_key, str) or raw_key.strip() == "":
                    raise ValueError(
                        _runtime_error(
                            location,
                            "value_weights contains an empty or non-string key",
                            "use non-empty string keys in value_weights",
                        )
                    )
                key = raw_key.strip()
                normalized_weights[key] = _parse_non_negative_float(
                    raw_weight,
                    location=location,
                    field_name=f"value_weights['{raw_key}']",
                    hint="use non-negative finite numeric weights",
                )
            default_weight = _parse_non_negative_float(
                raw_profile.get("default_weight", 1.0),
                location=location,
                field_name="default_weight",
                hint="set default_weight to a non-negative finite numeric value",
            )

            compiled_profile = {
                "profile_index": profile_index,
                "profile_id": profile_id,
                "table": table_name,
                "column": column_name,
                "dtype": column.dtype,
                "kind": "missingness",
                "where": where_predicates,
                "mechanism": mechanism,
                "base_rate": base_rate,
                "driver_column": driver_column,
                "value_weights": normalized_weights,
                "default_weight": default_weight,
            }
        elif kind == "quality_issue":
            issue_type = str(raw_profile.get("issue_type", "")).strip().lower()
            if issue_type not in {"format_error", "stale_value", "drift"}:
                raise ValueError(
                    _runtime_error(
                        location,
                        f"unsupported issue_type '{issue_type}'",
                        "set issue_type to 'format_error', 'stale_value', or 'drift'",
                    )
                )
            rate = _parse_probability(
                raw_profile.get("rate"),
                location=location,
                field_name="rate",
                hint="set rate to a numeric value between 0 and 1",
            )
            compiled_profile = {
                "profile_index": profile_index,
                "profile_id": profile_id,
                "table": table_name,
                "column": column_name,
                "dtype": column.dtype,
                "kind": "quality_issue",
                "where": where_predicates,
                "issue_type": issue_type,
                "rate": rate,
            }
            if issue_type == "format_error":
                replacement_raw = raw_profile.get("replacement")
                replacement: str | None = None
                if isinstance(replacement_raw, str) and replacement_raw.strip() != "":
                    replacement = replacement_raw
                compiled_profile["replacement"] = replacement
            elif issue_type == "stale_value":
                lag_rows = _parse_int(
                    raw_profile.get("lag_rows", 1),
                    location=location,
                    field_name="lag_rows",
                    hint="set lag_rows to an integer >= 1",
                )
                if lag_rows < 1:
                    raise ValueError(
                        _runtime_error(
                            location,
                            "lag_rows must be >= 1",
                            "set lag_rows to 1 or greater",
                        )
                    )
                compiled_profile["lag_rows"] = lag_rows
            else:
                if column.dtype not in {"int", "float", "decimal", "date", "datetime"}:
                    raise ValueError(
                        _runtime_error(
                            location,
                            f"drift does not support dtype '{column.dtype}'",
                            "target drift profiles to int/float/decimal/date/datetime columns",
                        )
                    )
                step_raw = raw_profile.get("step")
                if step_raw is None:
                    raise ValueError(
                        _runtime_error(
                            location,
                            "drift.step is required",
                            "set step to a non-zero numeric value (or integer days/seconds for date/datetime)",
                        )
                    )
                if column.dtype in {"date", "datetime"}:
                    step = _parse_int(
                        step_raw,
                        location=location,
                        field_name="drift.step",
                        hint="set drift.step to a non-zero integer number of days/seconds",
                    )
                    if step == 0:
                        raise ValueError(
                            _runtime_error(
                                location,
                                "drift.step cannot be zero",
                                "set drift.step to a non-zero integer number of days/seconds",
                            )
                        )
                else:
                    try:
                        step = float(step_raw)
                    except (TypeError, ValueError) as exc:
                        raise ValueError(
                            _runtime_error(
                                location,
                                "drift.step must be numeric",
                                "set drift.step to a non-zero numeric drift increment",
                            )
                        ) from exc
                    if (not math.isfinite(step)) or step == 0.0:
                        raise ValueError(
                            _runtime_error(
                                location,
                                "drift.step must be a non-zero finite numeric value",
                                "set drift.step to a non-zero numeric drift increment",
                            )
                        )
                start_index = _parse_int(
                    raw_profile.get("start_index", 1),
                    location=location,
                    field_name="start_index",
                    hint="set start_index to an integer >= 1",
                )
                if start_index < 1:
                    raise ValueError(
                        _runtime_error(
                            location,
                            "start_index must be >= 1",
                            "set start_index to 1 or greater",
                        )
                    )
                compiled_profile["step"] = step
                compiled_profile["start_index"] = start_index
        else:
            raise ValueError(
                _runtime_error(
                    location,
                    f"unsupported kind '{kind}'",
                    "set kind to 'missingness' or 'quality_issue'",
                )
            )

        compiled.setdefault(table_name, []).append(compiled_profile)

    return compiled


__all__ = ["_compile_data_quality_profiles"]
