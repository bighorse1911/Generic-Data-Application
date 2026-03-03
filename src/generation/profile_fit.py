"""Sample-profile fitting (DG07) helpers."""

from __future__ import annotations

import csv
from datetime import date, datetime, timezone

from src.generators import get_generator
from src.generation.common import _iso_datetime, _runtime_error
from src.project_paths import resolve_repo_path, to_repo_relative_path
from src.schema_project_model import ColumnSpec, SchemaProject, TableSpec

def _read_csv_profile_source(
    *,
    location: str,
    source: dict[str, object],
) -> tuple[str, int, list[str]]:
    path_raw = source.get("path")
    if not isinstance(path_raw, str) or path_raw.strip() == "":
        raise ValueError(
            _runtime_error(
                location,
                "sample_source.path is required",
                "set sample_source.path to an existing CSV file path",
            )
        )
    raw_path = path_raw.strip()
    resolved_path = resolve_repo_path(raw_path)
    if not resolved_path.exists():
        raise ValueError(
            _runtime_error(
                location,
                f"sample_source.path '{raw_path}' does not exist",
                "provide an existing CSV file path",
            )
        )

    has_header_raw = source.get("has_header", True)
    if not isinstance(has_header_raw, bool):
        raise ValueError(
            _runtime_error(
                location,
                "sample_source.has_header must be boolean when provided",
                "set sample_source.has_header to true or false",
            )
        )
    has_header = bool(has_header_raw)

    has_index = "column_index" in source
    has_name = "column_name" in source
    if has_index == has_name:
        raise ValueError(
            _runtime_error(
                location,
                "sample_source requires exactly one of column_index or column_name",
                "set either sample_source.column_index or sample_source.column_name",
            )
        )

    skip_empty_raw = source.get("skip_empty", True)
    if not isinstance(skip_empty_raw, bool):
        raise ValueError(
            _runtime_error(
                location,
                "sample_source.skip_empty must be boolean when provided",
                "set sample_source.skip_empty to true or false",
            )
        )
    skip_empty = bool(skip_empty_raw)

    rows: list[list[str]] = []
    with resolved_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(list(row))
    if not rows:
        raise ValueError(
            _runtime_error(
                location,
                f"sample CSV '{raw_path}' has no rows",
                "provide a CSV file with header/data rows for DG07 fitting",
            )
        )

    data_rows = rows
    resolved_index: int
    if has_header:
        header = rows[0]
        data_rows = rows[1:]
        if has_name:
            column_name_raw = source.get("column_name")
            column_name = str(column_name_raw).strip()
            if column_name not in header:
                raise ValueError(
                    _runtime_error(
                        location,
                        f"sample_source.column_name '{column_name}' was not found in CSV header",
                        "use an existing CSV header name or switch to column_index",
                    )
                )
            resolved_index = header.index(column_name)
        else:
            try:
                resolved_index = int(source.get("column_index"))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    _runtime_error(
                        location,
                        "sample_source.column_index must be an integer",
                        "set sample_source.column_index to 0 or greater",
                    )
                ) from exc
    else:
        if has_name:
            raise ValueError(
                _runtime_error(
                    location,
                    "sample_source.column_name requires sample_source.has_header=true",
                    "set has_header=true when using column_name or use column_index",
                )
            )
        try:
            resolved_index = int(source.get("column_index"))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _runtime_error(
                    location,
                    "sample_source.column_index must be an integer",
                    "set sample_source.column_index to 0 or greater",
                )
            ) from exc

    if resolved_index < 0:
        raise ValueError(
            _runtime_error(
                location,
                "sample_source.column_index cannot be negative",
                "set sample_source.column_index to 0 or greater",
            )
        )

    values: list[str] = []
    for row in data_rows:
        if resolved_index >= len(row):
            continue
        cell = row[resolved_index]
        if skip_empty and cell.strip() == "":
            continue
        values.append(cell)
    if not values:
        raise ValueError(
            _runtime_error(
                location,
                "sample_source produced zero eligible values",
                "point to a populated CSV column or disable skip_empty",
            )
        )

    normalized_path = to_repo_relative_path(raw_path)
    return normalized_path, resolved_index, values


def _infer_profile_from_values(
    *,
    location: str,
    dtype: str,
    source_path: str,
    source_column_index: int,
    values: list[str],
) -> tuple[str, dict[str, object]]:
    if dtype == "int":
        parsed: list[int] = []
        for raw_value in values:
            text = raw_value.strip()
            try:
                parsed.append(int(text))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    _runtime_error(
                        location,
                        f"sample value '{raw_value}' is not integer-like",
                        "clean sample values or use fixed_profile for non-integer source data",
                    )
                ) from exc
        return "uniform_int", {"min": min(parsed), "max": max(parsed)}

    if dtype in {"float", "decimal"}:
        parsed_numeric: list[float] = []
        for raw_value in values:
            text = raw_value.strip()
            try:
                parsed_numeric.append(float(text))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    _runtime_error(
                        location,
                        f"sample value '{raw_value}' is not numeric",
                        "clean sample values or use fixed_profile for non-numeric source data",
                    )
                ) from exc
        min_value = min(parsed_numeric)
        max_value = max(parsed_numeric)
        if min_value == max_value:
            return "uniform_float", {"min": min_value, "max": max_value}
        mean_value = sum(parsed_numeric) / len(parsed_numeric)
        variance = sum((value - mean_value) ** 2 for value in parsed_numeric) / len(parsed_numeric)
        stdev = variance ** 0.5
        if stdev <= 0.0:
            stdev = (max_value - min_value) / 6.0
        if stdev <= 0.0:
            stdev = 1.0
        return "normal", {"mean": mean_value, "stdev": stdev, "min": min_value, "max": max_value}

    if dtype == "text":
        counts: dict[str, int] = {}
        order: list[str] = []
        for value in values:
            if value not in counts:
                counts[value] = 0
                order.append(value)
            counts[value] += 1
        choices = order
        weights = [float(counts[value]) for value in choices]
        return "choice_weighted", {"choices": choices, "weights": weights}

    if dtype == "date":
        parsed_dates: list[date] = []
        for raw_value in values:
            text = raw_value.strip()
            try:
                parsed_dates.append(date.fromisoformat(text))
            except Exception as exc:
                raise ValueError(
                    _runtime_error(
                        location,
                        f"sample value '{raw_value}' is not a valid ISO date",
                        "clean sample values to 'YYYY-MM-DD' or use fixed_profile",
                    )
                ) from exc
        return "date", {"start": min(parsed_dates).isoformat(), "end": max(parsed_dates).isoformat()}

    if dtype == "datetime":
        parsed_datetimes: list[datetime] = []
        for raw_value in values:
            text = raw_value.strip()
            try:
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except Exception as exc:
                raise ValueError(
                    _runtime_error(
                        location,
                        f"sample value '{raw_value}' is not a valid ISO datetime",
                        "clean sample values to ISO datetime text or use fixed_profile",
                    )
                ) from exc
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            parsed_datetimes.append(dt)
        return "timestamp_utc", {
            "start": _iso_datetime(min(parsed_datetimes)),
            "end": _iso_datetime(max(parsed_datetimes)),
        }

    raise ValueError(
        _runtime_error(
            location,
            f"sample_source inference does not support dtype '{dtype}'",
            "use fixed_profile for this target dtype",
        )
    )


def _resolve_sample_profile_fits(project: SchemaProject) -> SchemaProject:
    fit_specs = project.sample_profile_fits
    if not fit_specs:
        return project

    table_map = {table.table_name: table for table in project.tables}
    overrides: dict[tuple[str, str], tuple[str, dict[str, object], list[str] | None]] = {}

    for fit_index, raw_fit in enumerate(fit_specs):
        location = f"Project sample_profile_fits[{fit_index}]"
        if not isinstance(raw_fit, dict):
            raise ValueError(
                _runtime_error(
                    location,
                    "fit must be an object",
                    "set each sample_profile_fits item to a JSON object",
                )
            )

        table_name = str(raw_fit.get("table", "")).strip()
        column_name = str(raw_fit.get("column", "")).strip()
        table = table_map.get(table_name)
        if table is None:
            raise ValueError(
                _runtime_error(
                    location,
                    f"table '{table_name}' was not found",
                    "use an existing table name for DG07 profile fits",
                )
            )
        column = next((candidate for candidate in table.columns if candidate.name == column_name), None)
        if column is None:
            raise ValueError(
                _runtime_error(
                    location,
                    f"column '{column_name}' was not found on table '{table_name}'",
                    "use an existing target column for DG07 profile fits",
                )
            )

        fixed_profile_raw = raw_fit.get("fixed_profile")
        if isinstance(fixed_profile_raw, dict):
            generator_raw = fixed_profile_raw.get("generator")
            if not isinstance(generator_raw, str) or generator_raw.strip() == "":
                raise ValueError(
                    _runtime_error(
                        location,
                        "fixed_profile.generator is required",
                        "set fixed_profile.generator to a registered generator id",
                    )
                )
            generator = generator_raw.strip()
            try:
                get_generator(generator)
            except KeyError as exc:
                raise ValueError(
                    _runtime_error(
                        location,
                        f"fixed_profile.generator '{generator}' is not registered",
                        "set fixed_profile.generator to a registered generator id",
                    )
                ) from exc
            params_raw = fixed_profile_raw.get("params", {})
            if not isinstance(params_raw, dict):
                raise ValueError(
                    _runtime_error(
                        location,
                        "fixed_profile.params must be an object when provided",
                        "set fixed_profile.params to a JSON object",
                    )
                )
            depends_on_raw = fixed_profile_raw.get("depends_on")
            depends_on: list[str] | None = None
            if isinstance(depends_on_raw, list):
                depends_on = [str(name).strip() for name in depends_on_raw if str(name).strip() != ""]
            overrides[(table_name, column_name)] = (generator, dict(params_raw), depends_on)
            continue

        sample_source_raw = raw_fit.get("sample_source")
        if not isinstance(sample_source_raw, dict):
            raise ValueError(
                _runtime_error(
                    location,
                    "requires fixed_profile or sample_source",
                    "set fixed_profile for frozen deterministic profiles or sample_source for CSV-driven inference",
                )
            )
        source_path, source_column_index, values = _read_csv_profile_source(
            location=location,
            source=sample_source_raw,
        )
        generator, params = _infer_profile_from_values(
            location=location,
            dtype=column.dtype,
            source_path=source_path,
            source_column_index=source_column_index,
            values=values,
        )
        if generator == "sample_csv":
            params["path"] = source_path
            params["column_index"] = source_column_index
        overrides[(table_name, column_name)] = (generator, params, None)

    new_tables: list[TableSpec] = []
    for table in project.tables:
        new_columns: list[ColumnSpec] = []
        for column in table.columns:
            key = (table.table_name, column.name)
            override = overrides.get(key)
            if override is None:
                new_columns.append(column)
                continue
            generator, params, depends_on = override
            updated = ColumnSpec(
                name=column.name,
                dtype=column.dtype,
                nullable=column.nullable,
                primary_key=column.primary_key,
                unique=column.unique,
                min_value=column.min_value,
                max_value=column.max_value,
                choices=column.choices,
                pattern=column.pattern,
                generator=generator,
                params=params,
                depends_on=(depends_on if depends_on is not None else column.depends_on),
            )
            new_columns.append(updated)
        new_tables.append(
            TableSpec(
                table_name=table.table_name,
                columns=new_columns,
                row_count=table.row_count,
                business_key=table.business_key,
                business_key_unique_count=table.business_key_unique_count,
                business_key_static_columns=table.business_key_static_columns,
                business_key_changing_columns=table.business_key_changing_columns,
                scd_mode=table.scd_mode,
                scd_tracked_columns=table.scd_tracked_columns,
                scd_active_from_column=table.scd_active_from_column,
                scd_active_to_column=table.scd_active_to_column,
                correlation_groups=table.correlation_groups,
            )
        )

    return SchemaProject(
        name=project.name,
        seed=project.seed,
        tables=new_tables,
        foreign_keys=project.foreign_keys,
        timeline_constraints=project.timeline_constraints,
        data_quality_profiles=project.data_quality_profiles,
        sample_profile_fits=project.sample_profile_fits,
        locale_identity_bundles=project.locale_identity_bundles,
    )


__all__ = ["_read_csv_profile_source", "_infer_profile_from_values", "_resolve_sample_profile_fits"]
