"""Correlation-group (DG01) helpers."""

from __future__ import annotations

import random

from src.generation.common import _stable_subseed
from src.schema_project_model import TableSpec, correlation_cholesky_lower

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


__all__ = ["_categorical_order_lookup", "_correlation_sort_key", "_apply_table_correlation_groups"]
