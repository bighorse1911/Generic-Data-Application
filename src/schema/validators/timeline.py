from __future__ import annotations

from src.schema.types import SchemaProject
from src.schema.types import TableSpec
from src.schema.validators.common import _parse_non_negative_int
from src.schema.validators.common import _validation_error


def validate_timeline_constraints(project: SchemaProject, *, table_map: dict[str, TableSpec]) -> None:
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



__all__ = ["validate_timeline_constraints"]
