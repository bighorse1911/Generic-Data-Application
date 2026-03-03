from __future__ import annotations

from src.project_paths import resolve_repo_path
from src.schema.types import SchemaProject
from src.schema.types import TableSpec
from src.schema.validators.common import _parse_non_negative_int
from src.schema.validators.common import _validation_error


def validate_sample_profile_fits(project: SchemaProject, *, table_map: dict[str, TableSpec]) -> None:
    sample_profile_fits = project.sample_profile_fits
    if sample_profile_fits is not None:
        if not isinstance(sample_profile_fits, list):
            raise ValueError(
                _validation_error(
                    "Project",
                    "sample_profile_fits must be a list when provided",
                    "set sample_profile_fits to a list of DG07 fit objects or omit sample_profile_fits",
                )
            )
        if len(sample_profile_fits) == 0:
            raise ValueError(
                _validation_error(
                    "Project",
                    "sample_profile_fits cannot be empty when provided",
                    "add one or more DG07 fit objects or omit sample_profile_fits",
                )
            )

        seen_fit_ids: set[str] = set()
        seen_targets: set[tuple[str, str]] = set()
        for fit_index, raw_fit in enumerate(sample_profile_fits):
            location = f"Project sample_profile_fits[{fit_index}]"
            if not isinstance(raw_fit, dict):
                raise ValueError(
                    _validation_error(
                        location,
                        "fit must be a JSON object",
                        "configure this DG07 fit as an object with fit_id, table, column, and sample_source/fixed_profile",
                    )
                )

            fit_id_raw = raw_fit.get("fit_id")
            if not isinstance(fit_id_raw, str) or fit_id_raw.strip() == "":
                raise ValueError(
                    _validation_error(
                        location,
                        "fit_id is required",
                        "set fit_id to a non-empty string",
                    )
                )
            fit_id = fit_id_raw.strip()
            if fit_id in seen_fit_ids:
                raise ValueError(
                    _validation_error(
                        "Project",
                        f"duplicate DG07 fit_id '{fit_id}'",
                        "use unique fit_id values in sample_profile_fits",
                    )
                )
            seen_fit_ids.add(fit_id)

            table_raw = raw_fit.get("table")
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
                        "use an existing table name for DG07 fits",
                    )
                )
            table_cols = {column.name: column for column in table.columns}

            column_raw = raw_fit.get("column")
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
                        "use an existing column name for DG07 fits",
                    )
                )
            if column.primary_key:
                raise ValueError(
                    _validation_error(
                        location,
                        f"column '{column_name}' cannot target a primary key",
                        "target a non-primary-key column for DG07 profile fitting",
                    )
                )
            target = (table_name, column_name)
            if target in seen_targets:
                raise ValueError(
                    _validation_error(
                        "Project",
                        f"multiple DG07 fits target '{table_name}.{column_name}'",
                        "define at most one DG07 fit per table + column target",
                    )
                )
            seen_targets.add(target)

            strategy_raw = raw_fit.get("strategy", "auto")
            if not isinstance(strategy_raw, str) or strategy_raw.strip() == "":
                raise ValueError(
                    _validation_error(
                        location,
                        "strategy must be a string when provided",
                        "set strategy to 'auto' or omit strategy",
                    )
                )
            strategy = strategy_raw.strip().lower()
            if strategy != "auto":
                raise ValueError(
                    _validation_error(
                        location,
                        f"unsupported strategy '{strategy_raw}'",
                        "set strategy to 'auto' for this release",
                    )
                )

            fixed_profile_raw = raw_fit.get("fixed_profile")
            sample_source_raw = raw_fit.get("sample_source")
            if fixed_profile_raw is None and sample_source_raw is None:
                raise ValueError(
                    _validation_error(
                        location,
                        "requires fixed_profile or sample_source",
                        "set fixed_profile for frozen deterministic profiles or sample_source for CSV-driven inference",
                    )
                )

            if fixed_profile_raw is not None:
                if not isinstance(fixed_profile_raw, dict):
                    raise ValueError(
                        _validation_error(
                            location,
                            "fixed_profile must be a JSON object when provided",
                            "set fixed_profile like {'generator': 'normal', 'params': {...}}",
                        )
                    )
                generator_raw = fixed_profile_raw.get("generator")
                if not isinstance(generator_raw, str) or generator_raw.strip() == "":
                    raise ValueError(
                        _validation_error(
                            location,
                            "fixed_profile.generator is required",
                            "set fixed_profile.generator to a non-empty generator id",
                        )
                    )
                params_raw = fixed_profile_raw.get("params", {})
                if not isinstance(params_raw, dict):
                    raise ValueError(
                        _validation_error(
                            location,
                            "fixed_profile.params must be a JSON object when provided",
                            "set fixed_profile.params to an object like {'min': 0, 'max': 100}",
                        )
                    )
                depends_on_raw = fixed_profile_raw.get("depends_on")
                if depends_on_raw is not None:
                    if not isinstance(depends_on_raw, list):
                        raise ValueError(
                            _validation_error(
                                location,
                                "fixed_profile.depends_on must be a list when provided",
                                "set fixed_profile.depends_on to a list of existing source column names",
                            )
                        )
                    if len(depends_on_raw) == 0:
                        raise ValueError(
                            _validation_error(
                                location,
                                "fixed_profile.depends_on cannot be empty when provided",
                                "add one or more source column names or omit fixed_profile.depends_on",
                            )
                        )
                    depends_on_names: list[str] = []
                    for dep in depends_on_raw:
                        if not isinstance(dep, str) or dep.strip() == "":
                            raise ValueError(
                                _validation_error(
                                    location,
                                    "fixed_profile.depends_on contains an empty or non-string value",
                                    "use non-empty source column names in fixed_profile.depends_on",
                                )
                            )
                        dep_name = dep.strip()
                        if dep_name == column_name:
                            raise ValueError(
                                _validation_error(
                                    location,
                                    "fixed_profile.depends_on cannot include the target column itself",
                                    "list only other source columns in fixed_profile.depends_on",
                                )
                            )
                        if dep_name not in table_cols:
                            raise ValueError(
                                _validation_error(
                                    location,
                                    f"fixed_profile.depends_on column '{dep_name}' was not found on table '{table_name}'",
                                    "use existing table columns in fixed_profile.depends_on",
                                )
                            )
                        depends_on_names.append(dep_name)
                    if len(set(depends_on_names)) != len(depends_on_names):
                        raise ValueError(
                            _validation_error(
                                location,
                                "fixed_profile.depends_on contains duplicate column names",
                                "list each dependency source column once",
                            )
                        )

            if sample_source_raw is not None:
                if not isinstance(sample_source_raw, dict):
                    raise ValueError(
                        _validation_error(
                            location,
                            "sample_source must be a JSON object when provided",
                            "set sample_source like {'path': 'tests/fixtures/sample.csv', 'column_index': 0}",
                        )
                    )
                if column.dtype in {"bool", "bytes"}:
                    raise ValueError(
                        _validation_error(
                            location,
                            f"sample_source inference does not support target dtype '{column.dtype}'",
                            "use fixed_profile for bool/bytes targets or change target dtype",
                        )
                    )

                path_raw = sample_source_raw.get("path")
                if not isinstance(path_raw, str) or path_raw.strip() == "":
                    raise ValueError(
                        _validation_error(
                            location,
                            "sample_source.path is required",
                            "set sample_source.path to an existing CSV file path",
                        )
                    )
                sample_path = path_raw.strip()
                resolved_path = resolve_repo_path(sample_path)
                if not resolved_path.exists():
                    raise ValueError(
                        _validation_error(
                            location,
                            f"sample_source.path '{sample_path}' does not exist",
                            "provide an existing CSV file path",
                        )
                    )

                has_header_raw = sample_source_raw.get("has_header", True)
                if not isinstance(has_header_raw, bool):
                    raise ValueError(
                        _validation_error(
                            location,
                            "sample_source.has_header must be boolean when provided",
                            "set sample_source.has_header to true or false",
                        )
                    )
                has_header = bool(has_header_raw)

                has_index = "column_index" in sample_source_raw
                has_name = "column_name" in sample_source_raw
                if has_index == has_name:
                    raise ValueError(
                        _validation_error(
                            location,
                            "sample_source requires exactly one of column_index or column_name",
                            "set either sample_source.column_index or sample_source.column_name",
                        )
                    )
                if has_index:
                    column_index = _parse_non_negative_int(
                        sample_source_raw.get("column_index"),
                        location=location,
                        field_name="sample_source.column_index",
                        hint="set sample_source.column_index to an integer >= 0",
                    )
                    if column_index < 0:
                        raise ValueError(
                            _validation_error(
                                location,
                                "sample_source.column_index cannot be negative",
                                "set sample_source.column_index to 0 or greater",
                            )
                        )
                else:
                    column_name_raw = sample_source_raw.get("column_name")
                    if not isinstance(column_name_raw, str) or column_name_raw.strip() == "":
                        raise ValueError(
                            _validation_error(
                                location,
                                "sample_source.column_name must be a non-empty string",
                                "set sample_source.column_name to a CSV header name",
                            )
                        )
                    if not has_header:
                        raise ValueError(
                            _validation_error(
                                location,
                                "sample_source.column_name requires sample_source.has_header=true",
                                "set has_header=true when using column_name or use column_index",
                            )
                        )

                skip_empty_raw = sample_source_raw.get("skip_empty", True)
                if not isinstance(skip_empty_raw, bool):
                    raise ValueError(
                        _validation_error(
                            location,
                            "sample_source.skip_empty must be boolean when provided",
                            "set sample_source.skip_empty to true or false",
                        )
                    )


__all__ = ["validate_sample_profile_fits"]
