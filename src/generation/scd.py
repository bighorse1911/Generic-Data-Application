"""Business-key and SCD helpers."""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone

from src.generation.common import _iso_date, _iso_datetime
from src.schema_project_model import ColumnSpec, ForeignKeySpec, TableSpec

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


__all__ = ["_table_pk_col_name", "_table_col_map", "_normalize_scd_mode", "_effective_scd_tracked_columns", "_business_key_is_already_unique", "_business_key_value_for_row", "_enforce_business_key_uniqueness", "_parse_business_key_unique_count", "_enforce_business_key_unique_count", "_mutate_scd_tracked_value", "_apply_scd2_history", "_apply_scd2_history_presized", "_apply_business_key_and_scd"]
