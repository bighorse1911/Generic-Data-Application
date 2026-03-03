"""Data-quality profile (DG06) row-application helpers."""

from __future__ import annotations

import random
from datetime import timedelta

from src.generation.common import (
    _iso_date,
    _iso_datetime,
    _parse_iso_date_value,
    _parse_iso_datetime_value,
    _runtime_error,
    _stable_subseed,
)
from src.generation.fk_assignment import _resolve_fk_parent_weight
from src.generation.quality_profiles_helpers import (
    _default_format_error_value,
    _profile_clamp_probability,
    _profile_matches_where,
    _profile_rate_triggered,
)
from src.schema_project_model import TableSpec


def _apply_table_data_quality_profiles(
    table: TableSpec,
    rows: list[dict[str, object]],
    *,
    project_seed: int,
    compiled_profiles: dict[str, list[dict[str, object]]],
) -> None:
    if not rows:
        return
    profiles = compiled_profiles.get(table.table_name, [])
    if not profiles:
        return

    for profile in profiles:
        profile_id = str(profile.get("profile_id", "profile"))
        profile_index = int(profile.get("profile_index", 0))
        column_name = str(profile.get("column", ""))
        dtype = str(profile.get("dtype", ""))
        where_predicates = profile.get("where")
        if not isinstance(where_predicates, list):
            where_predicates = []
        profile_rng = random.Random(
            _stable_subseed(project_seed, f"dg06:{table.table_name}:{profile_id}:{profile_index}")
        )

        kind = str(profile.get("kind", ""))
        if kind == "missingness":
            mechanism = str(profile.get("mechanism", ""))
            base_rate = float(profile.get("base_rate", 0.0))
            driver_column_raw = profile.get("driver_column")
            driver_column = str(driver_column_raw) if driver_column_raw is not None else None
            value_weights = profile.get("value_weights")
            if not isinstance(value_weights, dict):
                value_weights = {}
            normalized_weights = {str(key): float(value) for key, value in value_weights.items()}
            default_weight = float(profile.get("default_weight", 1.0))

            for row in rows:
                if where_predicates and not _profile_matches_where(row, where_predicates):
                    continue
                if row.get(column_name) is None:
                    continue

                effective_rate = base_rate
                if mechanism in {"mar", "mnar"}:
                    source_column = driver_column if mechanism == "mar" else column_name
                    source_value = row.get(source_column) if source_column else row.get(column_name)
                    weight = _resolve_fk_parent_weight(
                        source_value,
                        weights=normalized_weights,
                        default_weight=default_weight,
                    )
                    effective_rate = _profile_clamp_probability(base_rate * weight)
                if _profile_rate_triggered(profile_rng, effective_rate):
                    row[column_name] = None

        elif kind == "quality_issue":
            issue_type = str(profile.get("issue_type", ""))
            rate = float(profile.get("rate", 0.0))
            if issue_type == "format_error":
                replacement_raw = profile.get("replacement")
                replacement = (
                    str(replacement_raw)
                    if isinstance(replacement_raw, str) and replacement_raw.strip() != ""
                    else _default_format_error_value(dtype=dtype, profile_id=profile_id)
                )
                for row in rows:
                    if where_predicates and not _profile_matches_where(row, where_predicates):
                        continue
                    if row.get(column_name) is None:
                        continue
                    if _profile_rate_triggered(profile_rng, rate):
                        row[column_name] = replacement

            elif issue_type == "stale_value":
                lag_rows = int(profile.get("lag_rows", 1))
                if lag_rows < 1:
                    continue
                baseline_values = [row.get(column_name) for row in rows]
                for row_index, row in enumerate(rows):
                    if row_index < lag_rows:
                        continue
                    if where_predicates and not _profile_matches_where(row, where_predicates):
                        continue
                    if not _profile_rate_triggered(profile_rng, rate):
                        continue
                    stale_value = baseline_values[row_index - lag_rows]
                    if stale_value is None:
                        continue
                    row[column_name] = stale_value

            elif issue_type == "drift":
                step = profile.get("step")
                start_index = int(profile.get("start_index", 1))
                for row_index, row in enumerate(rows, start=1):
                    if row_index < start_index:
                        continue
                    if where_predicates and not _profile_matches_where(row, where_predicates):
                        continue
                    if not _profile_rate_triggered(profile_rng, rate):
                        continue
                    current_value = row.get(column_name)
                    if current_value is None:
                        continue
                    progress = row_index - start_index + 1
                    row_location = f"Table '{table.table_name}', row {row_index}, column '{column_name}'"

                    if dtype == "int":
                        try:
                            base_value = int(current_value)
                            delta = float(step) * float(progress)
                        except (TypeError, ValueError) as exc:
                            raise ValueError(
                                _runtime_error(
                                    row_location,
                                    f"DG06 drift expected integer-like value but found {current_value!r}",
                                    "ensure drift targets generated int values before DG06 mutation",
                                )
                            ) from exc
                        row[column_name] = int(round(base_value + delta))
                    elif dtype in {"float", "decimal"}:
                        try:
                            base_value = float(current_value)
                            delta = float(step) * float(progress)
                        except (TypeError, ValueError) as exc:
                            raise ValueError(
                                _runtime_error(
                                    row_location,
                                    f"DG06 drift expected numeric value but found {current_value!r}",
                                    "ensure drift targets generated numeric values before DG06 mutation",
                                )
                            ) from exc
                        row[column_name] = float(base_value + delta)
                    elif dtype == "date":
                        try:
                            base_value = _parse_iso_date_value(current_value)
                            delta_days = int(step) * progress
                        except Exception as exc:
                            raise ValueError(
                                _runtime_error(
                                    row_location,
                                    f"DG06 drift expected ISO date value but found {current_value!r}",
                                    "ensure drift targets parseable ISO date values before DG06 mutation",
                                )
                            ) from exc
                        row[column_name] = _iso_date(base_value + timedelta(days=delta_days))
                    elif dtype == "datetime":
                        try:
                            base_value = _parse_iso_datetime_value(current_value)
                            delta_seconds = int(step) * progress
                        except Exception as exc:
                            raise ValueError(
                                _runtime_error(
                                    row_location,
                                    f"DG06 drift expected ISO datetime value but found {current_value!r}",
                                    "ensure drift targets parseable ISO datetime values before DG06 mutation",
                                )
                            ) from exc
                        row[column_name] = _iso_datetime(base_value + timedelta(seconds=delta_seconds))
                    else:
                        raise ValueError(
                            _runtime_error(
                                row_location,
                                f"DG06 drift does not support dtype '{dtype}'",
                                "target drift profiles to int/float/decimal/date/datetime columns",
                            )
                        )


__all__ = ["_apply_table_data_quality_profiles"]
