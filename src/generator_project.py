import hashlib
import logging
import random
import re
from datetime import date, datetime, timedelta, timezone
from src.generators import GenContext, get_generator, reset_runtime_generator_state
from src.schema_project_model import (
    SchemaProject,
    TableSpec,
    ColumnSpec,
    ForeignKeySpec,
    correlation_cholesky_lower,
    validate_project,
)

logger = logging.getLogger("generator_project")


def _runtime_error(location: str, issue: str, hint: str) -> str:
    return f"{location}: {issue}. Fix: {hint}."


def _stable_subseed(base_seed: int, name: str) -> int:
    """
    Deterministically derive a per-table/per-feature seed from base_seed and a string name.
    Avoids Python's built-in hash() which is randomized between runs.
    """
    h = hashlib.sha256(f"{base_seed}:{name}".encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _iso_date(d: date) -> str:
    return d.isoformat()


def _iso_datetime(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _parse_iso_date_value(value: object) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError("not a date string")
    return date.fromisoformat(value.strip())


def _parse_iso_datetime_value(value: object) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value.strip() != "":
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        raise ValueError("not a datetime string")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def _parse_child_temporal_or_none(value: object, *, dtype: str) -> object | None:
    if value is None:
        return None
    try:
        if dtype == "date":
            return _parse_iso_date_value(value)
        return _parse_iso_datetime_value(value)
    except Exception:
        return None


def _fk_lookup_identity(value: object) -> tuple[str, object]:
    if value is None:
        return ("none", None)
    if isinstance(value, bool):
        return ("bool", bool(value))
    if isinstance(value, int):
        return ("int", int(value))
    if isinstance(value, float) and value.is_integer():
        return ("int", int(value))
    if isinstance(value, str):
        text = value.strip()
        if text != "":
            try:
                return ("int", int(text))
            except (TypeError, ValueError):
                return ("str", value)
        return ("str", value)
    return (type(value).__name__, repr(value))


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

def _maybe_null(col, ctx: GenContext) -> bool:
    # PKs cannot be null
    if getattr(col, "primary_key", False):
        return False

    params = getattr(col, "params", None) or {}
    null_rate = params.get("null_rate", None)
    if null_rate is None:
        return False

    r = float(null_rate)
    if r <= 0.0:
        return False
    if r >= 1.0:
        return True
    return ctx.rng.random() < r


def _apply_numeric_post(col, v: object) -> object:
    if v is None:
        return None
    if not isinstance(v, (int, float)):
        return v

    params = getattr(col, "params", None) or {}
    mn = params.get("clamp_min", None)
    mx = params.get("clamp_max", None)

    x = float(v)
    if mn is not None:
        x = max(float(mn), x)
    if mx is not None:
        x = min(float(mx), x)

    # If dtype says int, keep int
    if getattr(col, "dtype", "") == "int":
        return int(round(x))

    if getattr(col, "dtype", "") == "decimal":
        scale = params.get("scale", None)
        if scale is not None:
            x = round(x, int(scale))
        return float(x)

    return x


def _categorical_order_lookup(order_values: object) -> dict[object, int]:
    if not isinstance(order_values, list):
        return {}
    lookup: dict[object, int] = {}
    for idx, value in enumerate(order_values):
        if value not in lookup:
            lookup[value] = idx
        text_key = str(value)
        if text_key not in lookup:
            lookup[text_key] = idx
    return lookup


def _correlation_sort_key(value: object, *, categorical_order: dict[object, int]) -> tuple[int, float, str]:
    if value is None:
        return (0, 0.0, "")

    try:
        if value in categorical_order:
            return (1, float(categorical_order[value]), "")
    except TypeError:
        pass
    text_value = str(value)
    if text_value in categorical_order:
        return (1, float(categorical_order[text_value]), "")

    if isinstance(value, bool):
        return (2, 1.0 if value else 0.0, "")
    if isinstance(value, (int, float)):
        return (2, float(value), "")
    return (3, 0.0, text_value)


def _apply_table_correlation_groups(
    table: TableSpec,
    rows: list[dict[str, object]],
    *,
    project_seed: int,
) -> None:
    groups = table.correlation_groups
    if not rows or not groups:
        return
    if not isinstance(groups, list):
        return

    for group_index, raw_group in enumerate(groups):
        if not isinstance(raw_group, dict):
            continue
        columns_raw = raw_group.get("columns")
        matrix_raw = raw_group.get("rank_correlation")
        if not isinstance(columns_raw, list) or not isinstance(matrix_raw, list):
            continue
        columns = [name.strip() for name in columns_raw if isinstance(name, str) and name.strip() != ""]
        if len(columns) < 2:
            continue
        size = len(columns)
        if len(matrix_raw) != size:
            continue

        matrix: list[list[float]] = []
        matrix_valid = True
        for row_raw in matrix_raw:
            if not isinstance(row_raw, list) or len(row_raw) != size:
                matrix_valid = False
                break
            try:
                matrix.append([float(value) for value in row_raw])
            except (TypeError, ValueError):
                matrix_valid = False
                break
        if not matrix_valid:
            continue

        try:
            lower = correlation_cholesky_lower(matrix)
        except ValueError:
            continue

        try:
            strength = float(raw_group.get("strength", 1.0))
        except (TypeError, ValueError):
            strength = 1.0
        if strength <= 0.0:
            continue
        if strength > 1.0:
            strength = 1.0

        categorical_orders_raw = raw_group.get("categorical_orders")
        categorical_orders: dict[str, dict[object, int]] = {}
        if isinstance(categorical_orders_raw, dict):
            for key, value in categorical_orders_raw.items():
                if isinstance(key, str):
                    categorical_orders[key.strip()] = _categorical_order_lookup(value)

        eligible_indices = [
            idx
            for idx, row in enumerate(rows)
            if all(row.get(column_name) is not None for column_name in columns)
        ]
        if len(eligible_indices) < 2:
            continue

        sorted_values_by_column: dict[str, list[object]] = {}
        for column_name in columns:
            order_lookup = categorical_orders.get(column_name, {})
            ordered_row_indices = sorted(
                eligible_indices,
                key=lambda row_idx: (
                    _correlation_sort_key(rows[row_idx].get(column_name), categorical_order=order_lookup),
                    row_idx,
                ),
            )
            sorted_values_by_column[column_name] = [rows[row_idx].get(column_name) for row_idx in ordered_row_indices]

        group_id_raw = raw_group.get("group_id")
        if isinstance(group_id_raw, str) and group_id_raw.strip() != "":
            group_id = group_id_raw.strip()
        else:
            group_id = f"group_{group_index + 1}"
        group_rng = random.Random(_stable_subseed(project_seed, f"corr:{table.table_name}:{group_id}"))

        eligible_count = len(eligible_indices)
        scores: list[list[float]] = [[0.0 for _ in range(size)] for _ in range(eligible_count)]
        for local_idx in range(eligible_count):
            base_draw = [group_rng.gauss(0.0, 1.0) for _ in range(size)]
            correlated = [0.0 for _ in range(size)]
            for row_idx in range(size):
                total = 0.0
                for col_idx in range(row_idx + 1):
                    total += lower[row_idx][col_idx] * base_draw[col_idx]
                correlated[row_idx] = total
            if strength < 1.0:
                noise = [group_rng.gauss(0.0, 1.0) for _ in range(size)]
                for score_idx in range(size):
                    correlated[score_idx] = (strength * correlated[score_idx]) + (
                        (1.0 - strength) * noise[score_idx]
                    )
            scores[local_idx] = correlated

        for col_idx, column_name in enumerate(columns):
            ranked_local_indices = sorted(
                range(eligible_count),
                key=lambda local_idx: (scores[local_idx][col_idx], local_idx),
            )
            sorted_values = sorted_values_by_column.get(column_name, [])
            if len(sorted_values) != eligible_count:
                continue
            for rank_idx, local_idx in enumerate(ranked_local_indices):
                row_idx = eligible_indices[local_idx]
                rows[row_idx][column_name] = sorted_values[rank_idx]


def _gen_value(col: ColumnSpec, rng: random.Random, row_index: int, table_name: str, row: dict[str, object]) -> object:
    ctx = GenContext(row_index=row_index, table=table_name, row=row, rng=rng, column=col.name)

    # Nulls (probabilistic)
    if _maybe_null(col, ctx):
        return None

    # Generate
    if getattr(col, "generator", None):
        try:
            fn = get_generator(col.generator)  # type: ignore[arg-type]
        except KeyError as exc:
            raise ValueError(
                _runtime_error(
                    f"Table '{table_name}', column '{col.name}'",
                    f"unknown generator '{col.generator}'",
                    "choose a registered generator name in column.generator",
                )
            ) from exc
        params = col.params or {}
        try:
            v = fn(params, ctx)
        except KeyError as exc:
            missing = str(exc.args[0]) if exc.args else "unknown"
            raise ValueError(
                f"Table '{table_name}', column '{col.name}': generator '{col.generator}' is missing required params key '{missing}'. "
                "Fix: set the required key in params before generation."
            ) from exc

        # Optional numeric outliers (only when numeric)
        out_rate = float(params.get("outlier_rate", 0.0) or 0.0)
        out_scale = float(params.get("outlier_scale", 3.0) or 3.0)
        if out_rate > 0 and isinstance(v, (int, float)) and rng.random() < out_rate:
            v = float(v) * out_scale

    else:
        v = _gen_value_fallback(col, rng, row_index)

    # Post-processing
    v = _apply_numeric_post(col, v)

    # choices override (if set)
    if col.choices:
        v = rng.choice(col.choices)

    # regex validation (if set)
    if col.pattern and v is not None:
        import re
        if not re.fullmatch(col.pattern, str(v)):
            raise ValueError(
                _runtime_error(
                    f"Table '{table_name}', column '{col.name}'",
                    f"value '{v}' does not match pattern '{col.pattern}'",
                    "adjust the generator output or update the regex pattern",
                )
            )

    return v





def _gen_value_fallback(col: ColumnSpec, rng: random.Random, row_index: int) -> object:
    # Null handling
    if col.nullable and rng.random() < 0.05:  # 5% nulls
        return None

    # Primary key: deterministic increasing integer (1..N)
    if col.primary_key:
        return row_index

    # Choices override
    if col.choices is not None:
        return rng.choice(col.choices)

    if col.dtype == "int":
        lo = int(col.min_value) if col.min_value is not None else 0
        hi = int(col.max_value) if col.max_value is not None else 1000
        return rng.randint(lo, hi)

    if col.dtype in {"float", "decimal"}:
        lo = float(col.min_value) if col.min_value is not None else 0.0
        hi = float(col.max_value) if col.max_value is not None else 1000.0
        return round(rng.uniform(lo, hi), 2)

    if col.dtype == "bool":
        return 1 if rng.random() < 0.5 else 0

    if col.dtype == "date":
        base = date(2020, 1, 1)
        d = base + timedelta(days=rng.randint(0, 3650))
        return _iso_date(d)

    if col.dtype == "datetime":
        base = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=rng.randint(0, 10_000_000))
        dt = base - timedelta(seconds=rng.randint(0, 3600 * 24 * 30))
        return _iso_datetime(dt)

    if col.dtype == "text":
        pattern = re.compile(col.pattern) if col.pattern else None
        letters = "abcdefghijklmnopqrstuvwxyz"

        def candidate() -> str:
            length = rng.randint(5, 14)
            return "".join(rng.choice(letters) for _ in range(length))

        for _ in range(50):
            s = candidate()
            if pattern is None or pattern.fullmatch(s):
                return s
        return candidate()

    if col.dtype == "bytes":
        params = col.params if isinstance(col.params, dict) else {}
        try:
            min_len = int(params.get("min_length", 8))
        except (TypeError, ValueError):
            min_len = 8
        try:
            max_len = int(params.get("max_length", min_len))
        except (TypeError, ValueError):
            max_len = min_len
        min_len = max(0, min_len)
        max_len = max(min_len, max_len)
        size = rng.randint(min_len, max_len)
        return bytes(rng.getrandbits(8) for _ in range(size))

    raise ValueError(
        _runtime_error(
            f"Column '{col.name}'",
            f"unsupported dtype '{col.dtype}' during runtime fallback generation",
            "use a supported dtype or configure a compatible generator",
        )
    )


def _dependency_order(project: SchemaProject) -> list[str]:
    """
    Return table names in parent->child order using Kahn's algorithm.
    MVP guarantees <=1 FK per child, but algorithm works regardless.
    """
    table_names = [t.table_name for t in project.tables]
    deps = {t: set() for t in table_names}       # t depends on these
    rev = {t: set() for t in table_names}        # these depend on t

    for fk in project.foreign_keys:
        child = fk.child_table
        parent = fk.parent_table
        deps[child].add(parent)
        rev[parent].add(child)

    # Optional additional fk sort
    # fks_by_child: dict[str, list[ForeignKeySpec]] = {}
    # for fk in project.foreign_keys:
    #     fks_by_child.setdefault(fk.child_table, []).append(fk)

    # Kahn
    ready = [t for t in table_names if len(deps[t]) == 0]
    ready.sort()
    out = []

    while ready:
        n = ready.pop(0)
        out.append(n)
        for child in sorted(rev[n]):
            deps[child].discard(n)
            if len(deps[child]) == 0:
                ready.append(child)
                ready.sort()

    if len(out) != len(table_names):
        raise ValueError(
            _runtime_error(
                "Project foreign keys",
                "cycle detected in table dependency graph",
                "remove circular foreign key dependencies",
            )
        )

    return out


def _table_pk_col_name(table: TableSpec) -> str:
    return [c.name for c in table.columns if c.primary_key][0]


def _table_col_map(table: TableSpec) -> dict[str, ColumnSpec]:
    return {c.name: c for c in table.columns}


def _normalize_scd_mode(table: TableSpec) -> str | None:
    if not isinstance(table.scd_mode, str):
        return None
    mode = table.scd_mode.strip().lower()
    return mode or None


def _effective_scd_tracked_columns(table: TableSpec) -> list[str]:
    return list(table.business_key_changing_columns or table.scd_tracked_columns or [])


def _business_key_is_already_unique(rows: list[dict[str, object]], key_cols: list[str]) -> bool:
    if not rows:
        return True
    tuples = [tuple(r.get(k) for k in key_cols) for r in rows]
    if any(any(v is None for v in t) for t in tuples):
        return False
    return len(set(tuples)) == len(tuples)


def _business_key_value_for_row(col: ColumnSpec, *, table_name: str, row_num: int) -> object:
    if col.dtype == "int":
        return row_num
    if col.dtype in {"float", "decimal"}:
        return float(row_num)
    if col.dtype == "text":
        return f"{table_name}_{col.name}_{row_num}"
    if col.dtype == "date":
        return _iso_date(date(2020, 1, 1) + timedelta(days=row_num))
    if col.dtype == "datetime":
        return _iso_datetime(datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=row_num))
    raise ValueError(
        f"Table '{table_name}', column '{col.name}': unsupported business key dtype '{col.dtype}'. "
        "Fix: use int/text/decimal/date/datetime business_key columns."
    )


def _enforce_business_key_uniqueness(table: TableSpec, rows: list[dict[str, object]]) -> None:
    key_cols = list(table.business_key or [])
    if not key_cols or not rows:
        return
    if _business_key_is_already_unique(rows, key_cols):
        return

    col_map = _table_col_map(table)
    for row_num, row in enumerate(rows, start=1):
        for key_col in key_cols:
            row[key_col] = _business_key_value_for_row(
                col_map[key_col],
                table_name=table.table_name,
                row_num=row_num,
            )


def _parse_business_key_unique_count(table: TableSpec, *, row_total: int) -> int | None:
    raw_count = table.business_key_unique_count
    if raw_count is None:
        return None
    if isinstance(raw_count, bool):
        raise ValueError(
            f"Table '{table.table_name}': business_key_unique_count must be an integer when provided. "
            "Fix: set business_key_unique_count to a positive whole number."
        )
    try:
        count = int(raw_count)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Table '{table.table_name}': business_key_unique_count must be an integer when provided. "
            "Fix: set business_key_unique_count to a positive whole number."
        ) from exc

    if count <= 0:
        raise ValueError(
            f"Table '{table.table_name}': business_key_unique_count must be > 0. "
            "Fix: set business_key_unique_count to a positive whole number."
        )
    if count > row_total:
        raise ValueError(
            f"Table '{table.table_name}': business_key_unique_count={count} cannot exceed generated row count={row_total}. "
            "Fix: reduce business_key_unique_count or increase table row_count."
        )
    return count


def _enforce_business_key_unique_count(table: TableSpec, rows: list[dict[str, object]]) -> None:
    key_cols = list(table.business_key or [])
    target_unique = _parse_business_key_unique_count(table, row_total=len(rows))
    if target_unique is None or not rows:
        return
    if not key_cols:
        raise ValueError(
            f"Table '{table.table_name}': business_key_unique_count requires business_key. "
            "Fix: configure business_key columns before setting business_key_unique_count."
        )

    col_map = _table_col_map(table)
    key_values: list[tuple[object, ...]] = []
    for key_idx in range(1, target_unique + 1):
        key_values.append(
            tuple(
                _business_key_value_for_row(
                    col_map[key_col],
                    table_name=table.table_name,
                    row_num=key_idx,
                )
                for key_col in key_cols
            )
        )

    for row_idx, row in enumerate(rows):
        values = key_values[row_idx % target_unique]
        for key_col, value in zip(key_cols, values, strict=True):
            row[key_col] = value


def _mutate_scd_tracked_value(
    col: ColumnSpec,
    value: object,
    *,
    version_idx: int,
    rng: random.Random,
) -> object:
    if col.generator == "ordered_choice":
        params = col.params if isinstance(col.params, dict) else {}
        orders_raw = params.get("orders")
        if isinstance(orders_raw, dict) and orders_raw:
            sequences: list[list[object]] = [
                seq for seq in orders_raw.values() if isinstance(seq, list) and len(seq) > 0
            ]
            if sequences:
                seq_match: list[object] | None = None
                idx_match: int | None = None

                for seq in sequences:
                    for idx, item in enumerate(seq):
                        if item == value:
                            seq_match = seq
                            idx_match = idx
                            break
                    if seq_match is not None:
                        break

                if seq_match is None:
                    value_text = str(value)
                    for seq in sequences:
                        for idx, item in enumerate(seq):
                            if str(item) == value_text:
                                seq_match = seq
                                idx_match = idx
                                break
                        if seq_match is not None:
                            break

                if seq_match is None:
                    seq_match = sequences[0]
                    start_raw = params.get("start_index", 0)
                    try:
                        start_idx = int(start_raw)
                    except (TypeError, ValueError):
                        start_idx = 0
                    idx_match = max(0, min(start_idx, len(seq_match) - 1))

                move_weights = [0.0, 1.0]
                move_weights_raw = params.get("move_weights")
                if isinstance(move_weights_raw, list) and len(move_weights_raw) > 0:
                    parsed_weights: list[float] = []
                    for raw in move_weights_raw:
                        try:
                            weight = float(raw)
                        except (TypeError, ValueError):
                            parsed_weights = []
                            break
                        if weight < 0:
                            parsed_weights = []
                            break
                        parsed_weights.append(weight)
                    if parsed_weights and any(weight > 0 for weight in parsed_weights):
                        move_weights = parsed_weights

                out_idx = int(idx_match)
                steps = max(1, version_idx)
                for _ in range(steps):
                    step = rng.choices(range(len(move_weights)), weights=move_weights, k=1)[0]
                    out_idx = min(out_idx + int(step), len(seq_match) - 1)
                return seq_match[out_idx]

    if col.generator == "state_transition":
        params = col.params if isinstance(col.params, dict) else {}
        states_raw = params.get("states")
        transitions_raw = params.get("transitions")
        if not isinstance(states_raw, list) or len(states_raw) == 0:
            return value
        if not isinstance(transitions_raw, dict) or len(transitions_raw) == 0:
            return value

        state_kind: str | None = None
        states: list[object] = []
        for raw_state in states_raw:
            if isinstance(raw_state, bool) or isinstance(raw_state, (dict, list)):
                return value
            if isinstance(raw_state, int):
                kind = "int"
                normalized_state: object = int(raw_state)
            elif isinstance(raw_state, str):
                if raw_state.strip() == "":
                    return value
                kind = "text"
                normalized_state = raw_state
            else:
                return value
            if state_kind is None:
                state_kind = kind
            elif state_kind != kind:
                return value
            states.append(normalized_state)
        if state_kind is None:
            return value

        state_set = set(states)

        def _coerce_state(
            raw_state: object,
            *,
            allow_int_string: bool,
        ) -> object | None:
            if state_kind == "int":
                if isinstance(raw_state, bool):
                    return None
                if isinstance(raw_state, int):
                    normalized = int(raw_state)
                elif allow_int_string and isinstance(raw_state, str) and raw_state.strip() != "":
                    try:
                        normalized = int(raw_state.strip())
                    except (TypeError, ValueError):
                        return None
                else:
                    return None
            else:
                if not isinstance(raw_state, str):
                    return None
                normalized = raw_state
            if normalized not in state_set:
                return None
            return normalized

        terminal_raw = params.get("terminal_states", [])
        terminal_states: set[object] = set()
        if isinstance(terminal_raw, list):
            for raw_terminal in terminal_raw:
                normalized_terminal = _coerce_state(raw_terminal, allow_int_string=False)
                if normalized_terminal is not None:
                    terminal_states.add(normalized_terminal)

        transitions: dict[object, tuple[list[object], list[float]]] = {}
        for raw_from, raw_targets in transitions_raw.items():
            from_state = _coerce_state(raw_from, allow_int_string=True)
            if from_state is None or not isinstance(raw_targets, dict) or len(raw_targets) == 0:
                continue
            targets: list[object] = []
            weights: list[float] = []
            for raw_to, raw_weight in raw_targets.items():
                to_state = _coerce_state(raw_to, allow_int_string=True)
                if to_state is None or to_state == from_state:
                    continue
                try:
                    weight = float(raw_weight)
                except (TypeError, ValueError):
                    continue
                if weight < 0:
                    continue
                targets.append(to_state)
                weights.append(weight)
            if targets and any(weight > 0 for weight in weights):
                transitions[from_state] = (targets, weights)

        current_state = _coerce_state(value, allow_int_string=(state_kind == "int"))
        if current_state is None:
            start_state_raw = params.get("start_state")
            current_state = _coerce_state(start_state_raw, allow_int_string=False)
        if current_state is None:
            current_state = states[0]

        steps = max(1, version_idx)
        for _ in range(steps):
            if current_state in terminal_states:
                continue
            transition = transitions.get(current_state)
            if transition is None:
                continue
            targets, weights = transition
            if not any(weight > 0 for weight in weights):
                continue
            current_state = rng.choices(targets, weights=weights, k=1)[0]
        return current_state

    if col.dtype == "int":
        try:
            if isinstance(value, bool):
                base = int(value)
            elif isinstance(value, int):
                base = value
            elif isinstance(value, float) and value.is_integer():
                base = int(value)
            elif isinstance(value, str) and value.strip() != "":
                base = int(value.strip())
            else:
                return value
        except (TypeError, ValueError):
            return value
        return base + version_idx
    if col.dtype in {"float", "decimal"}:
        base = float(value) if isinstance(value, (int, float)) else 0.0
        return round(base + (0.1 * version_idx), 6)
    if col.dtype == "text":
        base = str(value) if value is not None else "value"
        return f"{base}_v{version_idx}"
    if col.dtype == "bool":
        if value in {0, False}:
            return 1
        return 0
    if col.dtype == "date":
        try:
            d = date.fromisoformat(str(value))
        except Exception:
            d = date(2020, 1, 1)
        return _iso_date(d + timedelta(days=version_idx))
    if col.dtype == "datetime":
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            dt = datetime(2020, 1, 1, tzinfo=timezone.utc)
        return _iso_datetime(dt + timedelta(hours=version_idx))
    # Fallback for unsupported/rare types under tracking.
    return value


def _apply_scd2_history(
    table: TableSpec,
    rows: list[dict[str, object]],
    rng: random.Random,
    *,
    incoming_fks: list[ForeignKeySpec] | None = None,
) -> list[dict[str, object]]:
    if not rows:
        return rows

    if not table.scd_active_from_column or not table.scd_active_to_column:
        raise ValueError(
            f"Table '{table.table_name}': scd2 generation requires scd_active_from_column and scd_active_to_column. "
            "Fix: set both active period columns in table config."
        )

    col_map = _table_col_map(table)
    pk_col = _table_pk_col_name(table)
    tracked_cols = _effective_scd_tracked_columns(table)
    static_cols = list(table.business_key_static_columns or [])
    start_col = table.scd_active_from_column
    end_col = table.scd_active_to_column
    active_dtype = col_map[start_col].dtype

    # For child-table SCD2, duplicate versions only when FK max_children capacity remains.
    fk_spare_capacity: list[tuple[ForeignKeySpec, dict[object, int]]] = []
    incoming_fks = list(incoming_fks or [])
    for fk in incoming_fks:
        counts_by_parent: dict[object, int] = {}
        for row in rows:
            parent_id = row.get(fk.child_column)
            counts_by_parent[parent_id] = counts_by_parent.get(parent_id, 0) + 1
        spare_by_parent = {
            parent_id: max(0, fk.max_children - count)
            for parent_id, count in counts_by_parent.items()
        }
        fk_spare_capacity.append((fk, spare_by_parent))

    expanded: list[dict[str, object]] = []

    for row_idx, base_row in enumerate(rows, start=1):
        # Deterministic behavior: every even key attempts a second version.
        # For child-table SCD2, we only duplicate when FK capacity allows it.
        allow_extra_version = True
        for fk, spare_by_parent in fk_spare_capacity:
            parent_id = base_row.get(fk.child_column)
            if spare_by_parent.get(parent_id, 0) <= 0:
                allow_extra_version = False
                break
        version_count = 2 if (row_idx % 2 == 0 and allow_extra_version) else 1
        if version_count > 1:
            for fk, spare_by_parent in fk_spare_capacity:
                parent_id = base_row.get(fk.child_column)
                spare_by_parent[parent_id] = max(0, spare_by_parent.get(parent_id, 0) - 1)
        base_offset_days = row_idx * 90

        for version_idx in range(version_count):
            out_row = dict(base_row)
            if version_idx > 0:
                for tracked_col in tracked_cols:
                    out_row[tracked_col] = _mutate_scd_tracked_value(
                        col_map[tracked_col],
                        out_row.get(tracked_col),
                        version_idx=version_idx,
                        rng=rng,
                    )
            for static_col in static_cols:
                out_row[static_col] = base_row.get(static_col)

            if active_dtype == "date":
                period_start = date(2020, 1, 1) + timedelta(days=base_offset_days + (version_idx * 30))
                if version_idx < version_count - 1:
                    next_start = date(2020, 1, 1) + timedelta(days=base_offset_days + ((version_idx + 1) * 30))
                    period_end = next_start - timedelta(days=1)
                    out_row[end_col] = _iso_date(period_end)
                else:
                    out_row[end_col] = "9999-12-31"
                out_row[start_col] = _iso_date(period_start)
            else:
                period_start_dt = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(
                    days=base_offset_days + (version_idx * 30)
                )
                if version_idx < version_count - 1:
                    next_start_dt = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(
                        days=base_offset_days + ((version_idx + 1) * 30)
                    )
                    period_end_dt = next_start_dt - timedelta(seconds=1)
                    out_row[end_col] = _iso_datetime(period_end_dt)
                else:
                    out_row[end_col] = "9999-12-31T23:59:59Z"
                out_row[start_col] = _iso_datetime(period_start_dt)

            expanded.append(out_row)

    for i, row in enumerate(expanded, start=1):
        row[pk_col] = i

    return expanded


def _apply_scd2_history_presized(
    table: TableSpec,
    rows: list[dict[str, object]],
    rng: random.Random,
) -> list[dict[str, object]]:
    if not rows:
        return rows

    key_cols = list(table.business_key or [])
    if not key_cols:
        return rows

    if not table.scd_active_from_column or not table.scd_active_to_column:
        raise ValueError(
            f"Table '{table.table_name}': scd2 generation requires scd_active_from_column and scd_active_to_column. "
            "Fix: set both active period columns in table config."
        )

    col_map = _table_col_map(table)
    pk_col = _table_pk_col_name(table)
    tracked_cols = _effective_scd_tracked_columns(table)
    static_cols = list(table.business_key_static_columns or [])
    start_col = table.scd_active_from_column
    end_col = table.scd_active_to_column
    active_dtype = col_map[start_col].dtype

    counts_by_key: dict[tuple[object, ...], int] = {}
    base_row_by_key: dict[tuple[object, ...], dict[str, object]] = {}
    key_order: list[tuple[object, ...]] = []
    for row in rows:
        key = tuple(row.get(col) for col in key_cols)
        if key not in counts_by_key:
            counts_by_key[key] = 0
            key_order.append(key)
            base_row_by_key[key] = dict(row)
        counts_by_key[key] += 1

    key_offsets = {key: idx for idx, key in enumerate(key_order, start=1)}
    seen_by_key: dict[tuple[object, ...], int] = {}
    expanded: list[dict[str, object]] = []

    for row in rows:
        key = tuple(row.get(col) for col in key_cols)
        version_idx = seen_by_key.get(key, 0)
        seen_by_key[key] = version_idx + 1
        version_count = counts_by_key[key]
        base_row = base_row_by_key[key]

        out_row = dict(row)
        if version_idx > 0:
            for tracked_col in tracked_cols:
                out_row[tracked_col] = _mutate_scd_tracked_value(
                    col_map[tracked_col],
                    base_row.get(tracked_col),
                    version_idx=version_idx,
                    rng=rng,
                )
        for static_col in static_cols:
            out_row[static_col] = base_row.get(static_col)

        base_offset_days = key_offsets[key] * 90
        if active_dtype == "date":
            period_start = date(2020, 1, 1) + timedelta(days=base_offset_days + (version_idx * 30))
            if version_idx < version_count - 1:
                next_start = date(2020, 1, 1) + timedelta(days=base_offset_days + ((version_idx + 1) * 30))
                out_row[end_col] = _iso_date(next_start - timedelta(days=1))
            else:
                out_row[end_col] = "9999-12-31"
            out_row[start_col] = _iso_date(period_start)
        else:
            period_start_dt = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(
                days=base_offset_days + (version_idx * 30)
            )
            if version_idx < version_count - 1:
                next_start_dt = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(
                    days=base_offset_days + ((version_idx + 1) * 30)
                )
                out_row[end_col] = _iso_datetime(next_start_dt - timedelta(seconds=1))
            else:
                out_row[end_col] = "9999-12-31T23:59:59Z"
            out_row[start_col] = _iso_datetime(period_start_dt)

        expanded.append(out_row)

    for i, row in enumerate(expanded, start=1):
        row[pk_col] = i
    return expanded


def _apply_business_key_and_scd(
    table: TableSpec,
    rows: list[dict[str, object]],
    rng: random.Random,
    *,
    incoming_fks: list[ForeignKeySpec] | None = None,
) -> list[dict[str, object]]:
    if not rows:
        return rows

    if table.business_key_unique_count is None:
        _enforce_business_key_uniqueness(table, rows)
    else:
        _enforce_business_key_unique_count(table, rows)

    scd_mode = _normalize_scd_mode(table)
    if scd_mode == "scd1" and table.business_key_unique_count is not None:
        key_cols = list(table.business_key or [])
        key_tuples = {tuple(row.get(col) for col in key_cols) for row in rows}
        if len(key_tuples) != len(rows):
            raise ValueError(
                f"Table '{table.table_name}': scd_mode='scd1' requires one row per business key, but generated rows ({len(rows)}) exceed unique business keys ({len(key_tuples)}). "
                "Fix: set business_key_unique_count equal to row_count for SCD1 tables."
            )
    if scd_mode == "scd2":
        if table.business_key_unique_count is not None:
            return _apply_scd2_history_presized(table, rows, rng)
        return _apply_scd2_history(table, rows, rng, incoming_fks=incoming_fks)
    return rows


def generate_project_rows(project: SchemaProject) -> dict[str, list[dict[str, object]]]:
    """
    Generates rows for all tables with valid PK/FK according to the project's foreign key rules.

    Returns: dict of table_name -> list of row dicts
    """
    reset_runtime_generator_state()
    validate_project(project)
    compiled_timeline_constraints = _compile_timeline_constraints(project)

    table_map: dict[str, TableSpec] = {t.table_name: t for t in project.tables}
    
    # CHANGE: allow multiple FKs per child table
    fks_by_child: dict[str, list[ForeignKeySpec]] = {}
    for fk in project.foreign_keys:
        fks_by_child.setdefault(fk.child_table, []).append(fk)

    order = _dependency_order(project)

    results: dict[str, list[dict[str, object]]] = {}
    pk_values: dict[str, list[int]] = {}  # table -> list of PK values

    # Helper: assign a FK column across rows while enforcing per-parent min/max constraints
    def _assign_fk_column(
        rng: random.Random,
        rows: list[dict[str, object]],
        child_fk_col: str,
        parent_ids: list[int],
        min_children: int,
        max_children: int,
        *,
        child_table: str,
        parent_table: str,
    ) -> None:
        """
        Assign rows[*][child_fk_col] such that each parent_id appears between min_children and max_children times.

        This requires:
            len(parent_ids) * min_children <= len(rows) <= len(parent_ids) * max_children
        """
        parent_n = len(parent_ids)
        total = len(rows)

        min_total = parent_n * min_children
        max_total = parent_n * max_children

        if total < min_total:
            raise ValueError(
                _runtime_error(
                    f"Table '{child_table}', FK column '{child_fk_col}'",
                    f"not enough rows to satisfy FK to parent table '{parent_table}' (need >= {min_total}, have {total})",
                    "increase child row_count or lower min_children",
                )
            )
        if total > max_total:
            raise ValueError(
                _runtime_error(
                    f"Table '{child_table}', FK column '{child_fk_col}'",
                    f"too many rows to satisfy FK to parent table '{parent_table}' (need <= {max_total}, have {total})",
                    "decrease child row_count or raise max_children",
                )
            )

        # Choose a count for each parent (within bounds), then adjust totals to match exactly
        counts = [min_children] * parent_n
        remaining = total - min_total

        # How many extra slots are available beyond mins?
        caps = [max_children - min_children] * parent_n

        # Distribute remaining across parents
        # (simple random allocation within caps)
        while remaining > 0:
            i = rng.randrange(parent_n)
            if caps[i] > 0:
                counts[i] += 1
                caps[i] -= 1
                remaining -= 1

        # Build the pool
        pool: list[int] = []
        for pid, k in zip(parent_ids, counts, strict=True):
            pool.extend([pid] * k)

        rng.shuffle(pool)

        # Assign
        for r, pid in zip(rows, pool, strict=True):
            r[child_fk_col] = pid

    for table_name in order:
        t = table_map[table_name]
        rng = random.Random(_stable_subseed(project.seed, f"table:{table_name}"))

        pk_col = _table_pk_col_name(t)
        incoming_fks = fks_by_child.get(table_name, [])
        ordered_cols = _order_columns_by_dependencies(t.columns)

        # -------------------------
        # ROOT TABLE (no incoming FK)
        # -------------------------
        if not incoming_fks:
            n = t.row_count
            rows: list[dict[str, object]] = []

            for i in range(1, n + 1):
                row: dict[str, object] = {}
                for col in ordered_cols:
                    row[col.name] = _gen_value(col, rng, i, table_name, row)

                rows.append(row)

            _apply_table_correlation_groups(t, rows, project_seed=project.seed)
            rows = _apply_business_key_and_scd(t, rows, rng, incoming_fks=incoming_fks)
            _enforce_table_timeline_constraints(
                t,
                rows,
                results=results,
                compiled_constraints=compiled_timeline_constraints,
            )

            # Defensive: ensure PK exists
            for r in rows:
                if r.get(pk_col) is None:
                    raise ValueError(
                        _runtime_error(
                            f"Table '{table_name}', column '{pk_col}'",
                            "primary key generated as null",
                            "set PK column nullable=false and use deterministic PK generation",
                        )
                    )

            # Extra defensive fill (should not normally trigger)
            for i, r in enumerate(rows, start=1):
                if r.get(pk_col) is None:
                    r[pk_col] = i

            results[table_name] = rows
            pk_values[table_name] = [int(r.get(pk_col)) for r in rows]
            logger.info("Generated root table '%s' rows=%d", table_name, len(rows))
            continue

        # -----------------------------------------
        # CHILD TABLE with exactly ONE incoming FK
        # (keep your existing logic unchanged)
        # -----------------------------------------
        if len(incoming_fks) == 1:
            fk = incoming_fks[0]
            parent_table_name = fk.parent_table
            parent_ids = pk_values[parent_table_name]

            rows: list[dict[str, object]] = []
            next_pk = 1

            for pid in parent_ids:
                k = rng.randint(fk.min_children, fk.max_children)
                for _ in range(k):
                    row: dict[str, object] = {}
                    for col in ordered_cols:
                        if col.name == fk.child_column:
                            row[col.name] = pid
                        else:
                            row[col.name] = _gen_value(col, rng, next_pk, table_name, row)
                    rows.append(row)
                    next_pk += 1

            _apply_table_correlation_groups(t, rows, project_seed=project.seed)
            rows = _apply_business_key_and_scd(t, rows, rng, incoming_fks=incoming_fks)
            _enforce_table_timeline_constraints(
                t,
                rows,
                results=results,
                compiled_constraints=compiled_timeline_constraints,
            )
            results[table_name] = rows
            pk_values[table_name] = [int(r[pk_col]) for r in rows]
            logger.info(
                "Generated child table '%s' rows=%d (parent=%s rows=%d, per-parent=%d..%d)",
                table_name, len(rows), parent_table_name, len(parent_ids), fk.min_children, fk.max_children
            )
            continue

        # -----------------------------------------
        # CHILD TABLE with MULTIPLE incoming FKs
        # Strategy: generate total rows = t.row_count, then assign each FK column.
        # -----------------------------------------
        # Compute allowed range intersection across all incoming FKs
        mins = []
        maxs = []
        for fk in incoming_fks:
            parent_ids = pk_values[fk.parent_table]
            mins.append(len(parent_ids) * fk.min_children)
            maxs.append(len(parent_ids) * fk.max_children)

        min_allowed = max(mins)
        max_allowed = min(maxs)

        if max_allowed < min_allowed:
            raise ValueError(
                _runtime_error(
                    f"Table '{table_name}'",
                    f"FK constraints produce an empty row_count range (min_allowed={min_allowed}, max_allowed={max_allowed})",
                    "adjust FK min_children/max_children so ranges overlap",
                )
            )

        # If user set row_count > 0, use it; else auto-pick a value in the intersection
        if t.row_count and t.row_count > 0:
            n = t.row_count
            if not (min_allowed <= n <= max_allowed):
                raise ValueError(
                    _runtime_error(
                        f"Table '{table_name}'",
                        f"row_count={n} is outside FK-constrained range [{min_allowed}, {max_allowed}]",
                        "set row_count within the allowed range or adjust FK bounds",
                    )
                )
        else:
            n = rng.randint(min_allowed, max_allowed)


        fk_cols = {fk.child_column for fk in incoming_fks}

        rows: list[dict[str, object]] = []
        for i in range(1, n + 1):
            row: dict[str, object] = {}
            for col in ordered_cols:
                if col.name in fk_cols:
                    # placeholder; we'll assign after parents exist
                    row[col.name] = None
                else:
                    row[col.name] = _gen_value(col, rng, i, table_name, row)
            rows.append(row)

        # Defensive: ensure PK exists
        for r in rows:
            if r.get(pk_col) is None:
                raise ValueError(
                    _runtime_error(
                        f"Table '{table_name}', column '{pk_col}'",
                        "primary key generated as null",
                        "set PK column nullable=false and use deterministic PK generation",
                    )
                )

        # Assign each FK column independently, enforcing its min/max rules
        for fk in incoming_fks:
            parent_ids = pk_values[fk.parent_table]
            # Use a stable subseed per FK so results are repeatable
            fk_rng = random.Random(_stable_subseed(project.seed, f"fk:{table_name}:{fk.child_column}:{fk.parent_table}"))

            _assign_fk_column(
                fk_rng,
                rows,
                fk.child_column,
                parent_ids,
                fk.min_children,
                fk.max_children,
                child_table=table_name,
                parent_table=fk.parent_table,
            )

        _apply_table_correlation_groups(t, rows, project_seed=project.seed)
        rows = _apply_business_key_and_scd(t, rows, rng, incoming_fks=incoming_fks)
        _enforce_table_timeline_constraints(
            t,
            rows,
            results=results,
            compiled_constraints=compiled_timeline_constraints,
        )
        results[table_name] = rows
        pk_values[table_name] = [int(r[pk_col]) for r in rows]

        logger.info(
            "Generated multi-FK child table '%s' rows=%d (incoming_fks=%d)",
            table_name, len(rows), len(incoming_fks)
        )

    return results

def _order_columns_by_dependencies(cols: list[ColumnSpec]) -> list[ColumnSpec]:
    """
    Topological-ish ordering for column dependencies within a row.
    - columns without depends_on first
    - then columns whose deps are satisfied
    Raises on cycles / missing deps.
    """
    remaining = list(cols)
    ordered: list[ColumnSpec] = []
    produced: set[str] = set()

    # pre-seed: treat columns with no depends as ready
    while remaining:
        progressed = False
        for c in list(remaining):
            deps = getattr(c, "depends_on", None) or []
            if all(d in produced for d in deps):
                ordered.append(c)
                produced.add(c.name)
                remaining.remove(c)
                progressed = True
        if not progressed:
            # cycle or missing dependency
            stuck = [(c.name, getattr(c, "depends_on", None)) for c in remaining]
            raise ValueError(
                _runtime_error(
                    "Column dependency ordering",
                    f"cannot resolve dependencies {stuck}",
                    "remove circular depends_on references and reference only existing columns",
                )
            )
    return ordered



def _assign_fk_column(
    rng: random.Random,
    rows: list[dict[str, object]],
    child_fk_col: str,
    parent_ids: list[int],
    min_children: int,
    max_children: int,
) -> None:
    """
    Assign values to rows[*][child_fk_col] such that each parent_id appears
    between min_children and max_children times (if possible).
    """

    parent_n = len(parent_ids)
    total = len(rows)

    min_total = parent_n * min_children
    max_total = parent_n * max_children

    if total < min_total:
        raise ValueError(
            _runtime_error(
                f"FK column '{child_fk_col}'",
                f"not enough rows to satisfy min_children (need >= {min_total}, have {total})",
                "increase child rows or lower min_children",
            )
        )
    if total > max_total:
        raise ValueError(
            _runtime_error(
                f"FK column '{child_fk_col}'",
                f"too many rows to satisfy max_children (need <= {max_total}, have {total})",
                "decrease child rows or raise max_children",
            )
        )

    # Build a pool with each parent repeated random(min..max) times
    pool: list[int] = []
    for pid in parent_ids:
        k = rng.randint(min_children, max_children)
        pool.extend([pid] * k)

    rng.shuffle(pool)

    # Adjust pool length to exactly total rows
    if len(pool) > total:
        pool = pool[:total]
    elif len(pool) < total:
        # Top up by sampling parents randomly
        pool.extend(rng.choices(parent_ids, k=(total - len(pool))))
        rng.shuffle(pool)

    # Assign one-to-one to rows
    for r, pid in zip(rows, pool, strict=True):
        r[child_fk_col] = pid
