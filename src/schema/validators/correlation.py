from __future__ import annotations

from src.schema.types import TableSpec
from src.schema.validators.common import _is_scalar_json_value
from src.schema.validators.common import _scalar_identity
from src.schema.validators.common import _validation_error

def correlation_cholesky_lower(matrix: list[list[float]]) -> list[list[float]]:
    """Return a lower-triangular factor for a positive semi-definite matrix."""
    size = len(matrix)
    lower: list[list[float]] = [[0.0 for _ in range(size)] for _ in range(size)]
    for row_idx in range(size):
        for col_idx in range(row_idx + 1):
            accum = 0.0
            for k in range(col_idx):
                accum += lower[row_idx][k] * lower[col_idx][k]
            if row_idx == col_idx:
                diagonal = matrix[row_idx][row_idx] - accum
                if diagonal < -1e-9:
                    raise ValueError("matrix is not positive semi-definite")
                lower[row_idx][col_idx] = (diagonal if diagonal > 0.0 else 0.0) ** 0.5
            else:
                pivot = lower[col_idx][col_idx]
                if abs(pivot) <= 1e-12:
                    lower[row_idx][col_idx] = 0.0
                else:
                    lower[row_idx][col_idx] = (matrix[row_idx][col_idx] - accum) / pivot
    return lower


def _validate_correlation_groups_for_table(
    table: TableSpec,
    *,
    col_map: dict[str, ColumnSpec],
    incoming_fk_cols: set[str],
) -> None:
    groups = table.correlation_groups
    if groups is None:
        return
    if not isinstance(groups, list):
        raise ValueError(
            _validation_error(
                f"Table '{table.table_name}'",
                "correlation_groups must be a list when provided",
                "set correlation_groups to a list of group objects or omit correlation_groups",
            )
        )
    if len(groups) == 0:
        raise ValueError(
            _validation_error(
                f"Table '{table.table_name}'",
                "correlation_groups cannot be empty when provided",
                "add one or more correlation groups or omit correlation_groups",
            )
        )

    seen_group_ids: set[str] = set()
    claimed_columns: dict[str, str] = {}
    business_key_cols = set(table.business_key or [])
    depends_on_by_column = {column.name: set(column.depends_on or []) for column in table.columns}

    for group_index, group in enumerate(groups):
        location = f"Table '{table.table_name}', correlation_groups[{group_index}]"
        if not isinstance(group, dict):
            raise ValueError(
                _validation_error(
                    location,
                    "group must be a JSON object",
                    "configure this correlation group as an object with group_id, columns, and rank_correlation",
                )
            )

        group_id_raw = group.get("group_id")
        if not isinstance(group_id_raw, str) or group_id_raw.strip() == "":
            raise ValueError(
                _validation_error(
                    location,
                    "group_id is required",
                    "set group_id to a non-empty string",
                )
            )
        group_id = group_id_raw.strip()
        if group_id in seen_group_ids:
            raise ValueError(
                _validation_error(
                    f"Table '{table.table_name}'",
                    f"duplicate correlation group_id '{group_id}'",
                    "use unique group_id values in correlation_groups",
                )
            )
        seen_group_ids.add(group_id)

        columns_raw = group.get("columns")
        if not isinstance(columns_raw, list) or len(columns_raw) < 2:
            raise ValueError(
                _validation_error(
                    location,
                    "columns must be a list with at least two column names",
                    "set columns to two or more existing non-key columns",
                )
            )
        columns: list[str] = []
        for column_raw in columns_raw:
            if not isinstance(column_raw, str) or column_raw.strip() == "":
                raise ValueError(
                    _validation_error(
                        location,
                        "columns contains an empty or non-string value",
                        "use non-empty column-name strings in columns",
                    )
                )
            columns.append(column_raw.strip())
        if len(set(columns)) != len(columns):
            raise ValueError(
                _validation_error(
                    location,
                    "columns contains duplicate names",
                    "list each correlation column only once",
                )
            )

        for column_name in columns:
            existing_group = claimed_columns.get(column_name)
            if existing_group is not None:
                raise ValueError(
                    _validation_error(
                        f"Table '{table.table_name}', column '{column_name}'",
                        f"is already assigned to correlation group '{existing_group}'",
                        "assign each column to at most one correlation group",
                    )
                )
            if column_name not in col_map:
                raise ValueError(
                    _validation_error(
                        location,
                        f"column '{column_name}' was not found",
                        "use existing column names in correlation_groups.columns",
                    )
                )
            column = col_map[column_name]
            if column.primary_key:
                raise ValueError(
                    _validation_error(
                        f"Table '{table.table_name}', column '{column_name}'",
                        "primary key columns cannot be in correlation groups",
                        "choose non-primary-key columns for correlation",
                    )
                )
            if column_name in incoming_fk_cols:
                raise ValueError(
                    _validation_error(
                        f"Table '{table.table_name}', column '{column_name}'",
                        "child foreign-key columns cannot be in correlation groups",
                        "choose non-FK columns for correlation",
                    )
                )
            if column_name in business_key_cols:
                raise ValueError(
                    _validation_error(
                        f"Table '{table.table_name}', column '{column_name}'",
                        "business_key columns cannot be in correlation groups",
                        "choose non-business-key columns for correlation",
                    )
                )
            if column.dtype == "bytes":
                raise ValueError(
                    _validation_error(
                        f"Table '{table.table_name}', column '{column_name}'",
                        "dtype 'bytes' is not supported in correlation groups",
                        "use numeric, text, bool, date, or datetime columns for correlation",
                    )
                )
            if len(column.depends_on or []) > 0:
                raise ValueError(
                    _validation_error(
                        f"Table '{table.table_name}', column '{column_name}'",
                        "columns with depends_on cannot be in correlation groups",
                        "remove depends_on from this column or exclude it from correlation_groups",
                    )
                )
            claimed_columns[column_name] = group_id

        for target_column, depends_on in depends_on_by_column.items():
            overlap = sorted(set(columns) & depends_on)
            if overlap:
                overlap_display = ", ".join(overlap)
                raise ValueError(
                    _validation_error(
                        location,
                        f"columns ({overlap_display}) are referenced by depends_on in column '{target_column}'",
                        "remove depends_on relationships involving correlation-group columns",
                    )
                )

        rank_raw = group.get("rank_correlation")
        expected_size = len(columns)
        if not isinstance(rank_raw, list) or len(rank_raw) != expected_size:
            raise ValueError(
                _validation_error(
                    location,
                    f"rank_correlation must be a {expected_size}x{expected_size} matrix",
                    "set rank_correlation rows/columns to match the columns list length",
                )
            )
        rank_matrix: list[list[float]] = []
        for row_index, row_raw in enumerate(rank_raw):
            if not isinstance(row_raw, list) or len(row_raw) != expected_size:
                raise ValueError(
                    _validation_error(
                        location,
                        f"rank_correlation row {row_index} must contain {expected_size} entries",
                        "set each rank_correlation row length to match the columns list length",
                    )
                )
            parsed_row: list[float] = []
            for col_index, value_raw in enumerate(row_raw):
                try:
                    value = float(value_raw)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        _validation_error(
                            location,
                            f"rank_correlation[{row_index}][{col_index}] must be numeric",
                            "use numeric correlation coefficients between -1 and 1",
                        )
                    ) from exc
                if value < -1.0 or value > 1.0:
                    raise ValueError(
                        _validation_error(
                            location,
                            f"rank_correlation[{row_index}][{col_index}]={value} is outside [-1, 1]",
                            "keep all correlation coefficients within -1 and 1",
                        )
                    )
                parsed_row.append(value)
            rank_matrix.append(parsed_row)

        for diag_index in range(expected_size):
            diagonal = rank_matrix[diag_index][diag_index]
            if abs(diagonal - 1.0) > 1e-6:
                raise ValueError(
                    _validation_error(
                        location,
                        f"rank_correlation diagonal at [{diag_index}][{diag_index}] must be 1.0",
                        "set all diagonal entries to 1.0",
                    )
                )
        for row_index in range(expected_size):
            for col_index in range(row_index + 1, expected_size):
                left = rank_matrix[row_index][col_index]
                right = rank_matrix[col_index][row_index]
                if abs(left - right) > 1e-6:
                    raise ValueError(
                        _validation_error(
                            location,
                            f"rank_correlation must be symmetric but [{row_index}][{col_index}]={left} and [{col_index}][{row_index}]={right}",
                            "set rank_correlation to a symmetric matrix",
                        )
                    )
        try:
            correlation_cholesky_lower(rank_matrix)
        except ValueError as exc:
            raise ValueError(
                _validation_error(
                    location,
                    "rank_correlation must be positive semi-definite",
                    "adjust coefficients to a valid correlation matrix",
                )
            ) from exc

        strength_raw = group.get("strength", 1.0)
        try:
            strength = float(strength_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _validation_error(
                    location,
                    "strength must be numeric when provided",
                    "set strength to a numeric value between 0 and 1",
                )
            ) from exc
        if strength < 0.0 or strength > 1.0:
            raise ValueError(
                _validation_error(
                    location,
                    f"strength {strength} is outside [0, 1]",
                    "set strength to a value between 0 and 1",
                )
            )

        categorical_orders_raw = group.get("categorical_orders")
        if categorical_orders_raw is not None:
            if not isinstance(categorical_orders_raw, dict):
                raise ValueError(
                    _validation_error(
                        location,
                        "categorical_orders must be an object when provided",
                        "set categorical_orders to an object mapping column names to ordered scalar lists",
                    )
                )
            for order_column_raw, order_values_raw in categorical_orders_raw.items():
                if not isinstance(order_column_raw, str) or order_column_raw.strip() == "":
                    raise ValueError(
                        _validation_error(
                            location,
                            "categorical_orders contains an empty or non-string column key",
                            "use non-empty column names as categorical_orders keys",
                        )
                    )
                order_column = order_column_raw.strip()
                if order_column not in columns:
                    raise ValueError(
                        _validation_error(
                            location,
                            f"categorical_orders key '{order_column}' must also be listed in columns",
                            "add the column to this group's columns list or remove the categorical_orders key",
                        )
                    )
                if not isinstance(order_values_raw, list) or len(order_values_raw) == 0:
                    raise ValueError(
                        _validation_error(
                            location,
                            f"categorical_orders['{order_column}'] must be a non-empty list",
                            "provide one or more ordered scalar values for this column",
                        )
                    )
                seen_values: set[tuple[str, str]] = set()
                for value in order_values_raw:
                    if not _is_scalar_json_value(value):
                        raise ValueError(
                            _validation_error(
                                location,
                                f"categorical_orders['{order_column}'] values must be scalar",
                                "use scalar values (string/number/bool/null) in categorical_orders",
                            )
                        )
                    marker = _scalar_identity(value)
                    if marker in seen_values:
                        raise ValueError(
                            _validation_error(
                                location,
                                f"categorical_orders['{order_column}'] contains duplicate values",
                                "list each ordered categorical value only once",
                            )
                        )
                    seen_values.add(marker)


__all__ = ["correlation_cholesky_lower", "_validate_correlation_groups_for_table"]
