"""Timeline (DG03) generation helpers."""

from __future__ import annotations

from datetime import timedelta

from src.generation.common import _iso_date, _iso_datetime, _parse_iso_date_value, _parse_iso_datetime_value, _runtime_error
from src.generation.fk_assignment import _fk_lookup_identity
from src.schema_project_model import SchemaProject

def _parse_child_temporal_or_none(value: object, *, dtype: str) -> object | None:
    if value is None:
        return None
    try:
        if dtype == "date":
            return _parse_iso_date_value(value)
        return _parse_iso_datetime_value(value)
    except Exception:
        return None


def _compile_timeline_constraints(project: SchemaProject) -> dict[str, list[dict[str, object]]]:
    raw_rules = project.timeline_constraints
    if not raw_rules:
        return {}

    table_map = {table.table_name: table for table in project.tables}
    fk_parent_pk_by_edge: dict[tuple[str, str, str], str] = {}
    for fk in project.foreign_keys:
        fk_parent_pk_by_edge[(fk.child_table, fk.child_column, fk.parent_table)] = fk.parent_column

    compiled: dict[str, list[dict[str, object]]] = {}
    for index, raw_rule in enumerate(raw_rules):
        if not isinstance(raw_rule, dict):
            continue
        child_table = str(raw_rule.get("child_table", "")).strip()
        child_column = str(raw_rule.get("child_column", "")).strip()
        if child_table == "" or child_column == "":
            continue

        table = table_map.get(child_table)
        if table is None:
            continue
        child_dtype: str | None = None
        for column in table.columns:
            if column.name == child_column:
                child_dtype = column.dtype
                break
        if child_dtype not in {"date", "datetime"}:
            continue

        mode = str(raw_rule.get("mode", "enforce")).strip().lower()
        if mode != "enforce":
            continue

        references_raw = raw_rule.get("references")
        if not isinstance(references_raw, list) or len(references_raw) == 0:
            continue

        rule_id_raw = raw_rule.get("rule_id")
        if isinstance(rule_id_raw, str) and rule_id_raw.strip() != "":
            rule_id = rule_id_raw.strip()
        else:
            rule_id = f"rule_{index + 1}"

        compiled_references: list[dict[str, object]] = []
        for ref_index, raw_reference in enumerate(references_raw):
            if not isinstance(raw_reference, dict):
                continue
            parent_table = str(raw_reference.get("parent_table", "")).strip()
            parent_column = str(raw_reference.get("parent_column", "")).strip()
            via_child_fk = str(raw_reference.get("via_child_fk", "")).strip()
            direction = str(raw_reference.get("direction", "")).strip().lower()
            parent_pk_column = fk_parent_pk_by_edge.get((child_table, via_child_fk, parent_table))
            if (
                parent_table == ""
                or parent_column == ""
                or via_child_fk == ""
                or direction not in {"after", "before"}
                or not isinstance(parent_pk_column, str)
                or parent_pk_column.strip() == ""
            ):
                continue

            if child_dtype == "date":
                try:
                    min_offset = int(raw_reference.get("min_days", 0))
                    max_offset = int(raw_reference.get("max_days", min_offset))
                except (TypeError, ValueError):
                    continue
            else:
                try:
                    min_offset = int(raw_reference.get("min_seconds", 0))
                    max_offset = int(raw_reference.get("max_seconds", min_offset))
                except (TypeError, ValueError):
                    continue
            if min_offset < 0 or max_offset < min_offset:
                continue

            compiled_references.append(
                {
                    "reference_index": ref_index,
                    "parent_table": parent_table,
                    "parent_column": parent_column,
                    "parent_pk_column": parent_pk_column,
                    "via_child_fk": via_child_fk,
                    "direction": direction,
                    "min_offset": min_offset,
                    "max_offset": max_offset,
                }
            )

        if not compiled_references:
            continue

        compiled.setdefault(child_table, []).append(
            {
                "rule_index": index,
                "rule_id": rule_id,
                "child_column": child_column,
                "dtype": child_dtype,
                "references": compiled_references,
            }
        )

    return compiled


def _build_parent_lookup(
    parent_rows: list[dict[str, object]],
    *,
    parent_table: str,
    parent_pk_column: str,
) -> dict[tuple[str, object], dict[str, object]]:
    lookup: dict[tuple[str, object], dict[str, object]] = {}
    for idx, row in enumerate(parent_rows, start=1):
        key_raw = row.get(parent_pk_column)
        if key_raw is None:
            raise ValueError(
                _runtime_error(
                    f"Table '{parent_table}', row {idx}, column '{parent_pk_column}'",
                    "parent lookup key is null during DG03 timeline enforcement",
                    "ensure parent PK values are generated and non-null before timeline enforcement",
                )
            )
        lookup[_fk_lookup_identity(key_raw)] = row
    return lookup


def _enforce_table_timeline_constraints(
    table: TableSpec,
    rows: list[dict[str, object]],
    *,
    results: dict[str, list[dict[str, object]]],
    compiled_constraints: dict[str, list[dict[str, object]]],
) -> None:
    if not rows:
        return
    rules = compiled_constraints.get(table.table_name, [])
    if not rules:
        return

    parent_lookup_cache: dict[tuple[str, str], dict[tuple[str, object], dict[str, object]]] = {}

    for rule in rules:
        child_column = str(rule.get("child_column"))
        dtype = str(rule.get("dtype"))
        rule_id = str(rule.get("rule_id"))
        references = rule.get("references")
        if dtype not in {"date", "datetime"} or not isinstance(references, list) or not references:
            continue

        for row_index, row in enumerate(rows, start=1):
            row_location = f"Table '{table.table_name}', row {row_index}, column '{child_column}'"

            lower_bound: object | None = None
            upper_bound: object | None = None

            for raw_reference in references:
                if not isinstance(raw_reference, dict):
                    continue
                parent_table = str(raw_reference.get("parent_table"))
                parent_column = str(raw_reference.get("parent_column"))
                parent_pk_column = str(raw_reference.get("parent_pk_column"))
                via_child_fk = str(raw_reference.get("via_child_fk"))
                direction = str(raw_reference.get("direction")).lower()
                min_offset = int(raw_reference.get("min_offset", 0))
                max_offset = int(raw_reference.get("max_offset", min_offset))

                parent_rows = results.get(parent_table)
                if parent_rows is None:
                    raise ValueError(
                        _runtime_error(
                            row_location,
                            f"parent table '{parent_table}' rows are unavailable for DG03 timeline enforcement",
                            "ensure parent tables are generated before constrained child tables",
                        )
                    )

                cache_key = (parent_table, parent_pk_column)
                if cache_key not in parent_lookup_cache:
                    parent_lookup_cache[cache_key] = _build_parent_lookup(
                        parent_rows,
                        parent_table=parent_table,
                        parent_pk_column=parent_pk_column,
                    )
                parent_lookup = parent_lookup_cache[cache_key]

                fk_value_raw = row.get(via_child_fk)
                if fk_value_raw is None:
                    raise ValueError(
                        _runtime_error(
                            row_location,
                            f"child FK '{via_child_fk}' is null and cannot resolve parent '{parent_table}'",
                            "ensure FK assignment occurs before DG03 timeline enforcement",
                        )
                    )
                parent_row = parent_lookup.get(_fk_lookup_identity(fk_value_raw))
                if parent_row is None:
                    raise ValueError(
                        _runtime_error(
                            row_location,
                            (
                                f"could not resolve parent row in '{parent_table}' via "
                                f"child FK '{via_child_fk}' value '{fk_value_raw}'"
                            ),
                            "ensure FK values map to existing parent keys before DG03 timeline enforcement",
                        )
                    )

                parent_value_raw = parent_row.get(parent_column)
                if dtype == "date":
                    try:
                        parent_value = _parse_iso_date_value(parent_value_raw)
                    except Exception as exc:
                        raise ValueError(
                            _runtime_error(
                                row_location,
                                (
                                    f"parent value '{parent_table}.{parent_column}' is not a valid ISO date "
                                    f"(value={parent_value_raw!r})"
                                ),
                                "fix parent temporal values to valid 'YYYY-MM-DD' dates",
                            )
                        ) from exc
                    if direction == "after":
                        reference_lower = parent_value + timedelta(days=min_offset)
                        reference_upper = parent_value + timedelta(days=max_offset)
                    else:
                        reference_lower = parent_value - timedelta(days=max_offset)
                        reference_upper = parent_value - timedelta(days=min_offset)
                else:
                    try:
                        parent_value = _parse_iso_datetime_value(parent_value_raw)
                    except Exception as exc:
                        raise ValueError(
                            _runtime_error(
                                row_location,
                                (
                                    f"parent value '{parent_table}.{parent_column}' is not a valid ISO datetime "
                                    f"(value={parent_value_raw!r})"
                                ),
                                "fix parent temporal values to valid ISO datetimes with UTC-compatible timezone",
                            )
                        ) from exc
                    if direction == "after":
                        reference_lower = parent_value + timedelta(seconds=min_offset)
                        reference_upper = parent_value + timedelta(seconds=max_offset)
                    else:
                        reference_lower = parent_value - timedelta(seconds=max_offset)
                        reference_upper = parent_value - timedelta(seconds=min_offset)

                if lower_bound is None or reference_lower > lower_bound:
                    lower_bound = reference_lower
                if upper_bound is None or reference_upper < upper_bound:
                    upper_bound = reference_upper

            if lower_bound is None or upper_bound is None:
                continue
            if lower_bound > upper_bound:
                raise ValueError(
                    _runtime_error(
                        row_location,
                        f"timeline interval intersection is empty for DG03 rule '{rule_id}'",
                        "adjust DG03 direction/min/max offsets so parent-derived intervals overlap",
                    )
                )

            child_value_raw = row.get(child_column)
            child_value = _parse_child_temporal_or_none(child_value_raw, dtype=dtype)

            if child_value is not None and lower_bound <= child_value <= upper_bound:
                continue

            if child_value is None or child_value < lower_bound:
                replacement = lower_bound
            elif child_value > upper_bound:
                replacement = upper_bound
            else:
                replacement = lower_bound

            if dtype == "date":
                row[child_column] = _iso_date(replacement)
            else:
                row[child_column] = _iso_datetime(replacement)


__all__ = ["_parse_child_temporal_or_none", "_compile_timeline_constraints", "_build_parent_lookup", "_enforce_table_timeline_constraints"]
