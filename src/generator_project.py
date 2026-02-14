import hashlib
import logging
import random
import re
from datetime import date, datetime, timedelta, timezone
from src.generators import GenContext, get_generator, reset_runtime_generator_state
from src.schema_project_model import SchemaProject, TableSpec, ColumnSpec, ForeignKeySpec, validate_project

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

            rows = _apply_business_key_and_scd(t, rows, rng, incoming_fks=incoming_fks)

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

            rows = _apply_business_key_and_scd(t, rows, rng, incoming_fks=incoming_fks)
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

        rows = _apply_business_key_and_scd(t, rows, rng, incoming_fks=incoming_fks)
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
