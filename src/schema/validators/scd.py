from __future__ import annotations

from src.schema.types import ColumnSpec
from src.schema.types import TableSpec


def validate_table_scd_and_business_key(
    t: TableSpec,
    *,
    col_map: dict[str, ColumnSpec],
    incoming_fk_cols: set[str],
) -> None:
    business_key = t.business_key
    business_key_unique_count = t.business_key_unique_count
    if business_key_unique_count is not None:
        if isinstance(business_key_unique_count, bool) or not isinstance(business_key_unique_count, int):
            raise ValueError(
                f"Table '{t.table_name}': business_key_unique_count must be an integer when provided. "
                "Fix: set business_key_unique_count to a positive whole number or omit it."
            )
        if business_key_unique_count <= 0:
            raise ValueError(
                f"Table '{t.table_name}': business_key_unique_count must be > 0. "
                "Fix: set business_key_unique_count to a positive whole number."
            )
        if not business_key:
            raise ValueError(
                f"Table '{t.table_name}': business_key_unique_count requires business_key. "
                "Fix: configure business_key columns before setting business_key_unique_count."
            )
        if t.row_count > 0 and business_key_unique_count > t.row_count:
            raise ValueError(
                f"Table '{t.table_name}': business_key_unique_count={business_key_unique_count} cannot exceed row_count={t.row_count}. "
                "Fix: set business_key_unique_count <= row_count, or increase row_count."
            )
    if business_key is not None:
        if len(business_key) == 0:
            raise ValueError(
                f"Table '{t.table_name}': business_key cannot be empty. "
                "Fix: provide one or more existing column names or omit business_key."
            )
        for name in business_key:
            if name not in col_map:
                raise ValueError(
                    f"Table '{t.table_name}': business_key column '{name}' not found. "
                    "Fix: use existing column names in business_key."
                )
            c = col_map[name]
            if c.nullable:
                raise ValueError(
                    f"Table '{t.table_name}', column '{name}': business_key columns must be non-nullable. "
                    "Fix: set nullable=false for business_key columns."
                )
            if c.dtype in {"bool", "bytes"}:
                raise ValueError(
                    f"Table '{t.table_name}', column '{name}': dtype '{c.dtype}' is not supported for business_key. "
                    "Fix: use a stable business identifier column with dtype int/text/decimal/date/datetime."
                )
            if name in incoming_fk_cols:
                raise ValueError(
                    f"Table '{t.table_name}', column '{name}': business_key cannot use incoming FK child column. "
                    "Fix: choose non-FK columns for business_key on child tables."
                )

    business_key_static_columns = t.business_key_static_columns
    if business_key_static_columns is not None:
        if len(business_key_static_columns) == 0:
            raise ValueError(
                f"Table '{t.table_name}': business_key_static_columns cannot be empty. "
                "Fix: provide one or more existing column names or omit business_key_static_columns."
            )
        if len(set(business_key_static_columns)) != len(business_key_static_columns):
            raise ValueError(
                f"Table '{t.table_name}': business_key_static_columns contains duplicate column names. "
                "Fix: list each static column only once."
            )
        for name in business_key_static_columns:
            if name not in col_map:
                raise ValueError(
                    f"Table '{t.table_name}': business_key_static_columns includes unknown column '{name}'. "
                    "Fix: use existing column names in business_key_static_columns."
                )

    business_key_changing_columns = t.business_key_changing_columns
    if business_key_changing_columns is not None:
        if len(business_key_changing_columns) == 0:
            raise ValueError(
                f"Table '{t.table_name}': business_key_changing_columns cannot be empty. "
                "Fix: provide one or more existing column names or omit business_key_changing_columns."
            )
        if len(set(business_key_changing_columns)) != len(business_key_changing_columns):
            raise ValueError(
                f"Table '{t.table_name}': business_key_changing_columns contains duplicate column names. "
                "Fix: list each changing column only once."
            )
        for name in business_key_changing_columns:
            if name not in col_map:
                raise ValueError(
                    f"Table '{t.table_name}': business_key_changing_columns includes unknown column '{name}'. "
                    "Fix: use existing column names in business_key_changing_columns."
                )
            if business_key and name in business_key:
                raise ValueError(
                    f"Table '{t.table_name}', column '{name}': business_key columns cannot be in business_key_changing_columns. "
                    "Fix: keep business_key columns stable and choose non-business-key changing columns."
                )

    if business_key_static_columns and business_key_changing_columns:
        overlap = sorted(set(business_key_static_columns) & set(business_key_changing_columns))
        if overlap:
            overlap_display = ", ".join(overlap)
            raise ValueError(
                f"Table '{t.table_name}': business_key_static_columns and business_key_changing_columns overlap ({overlap_display}). "
                "Fix: put each column in only one business-key behavior list."
            )

    scd_mode_raw = t.scd_mode.strip().lower() if isinstance(t.scd_mode, str) else ""
    scd_mode = scd_mode_raw or None
    if scd_mode not in {None, "scd1", "scd2"}:
        raise ValueError(
            f"Table '{t.table_name}': unsupported scd_mode '{t.scd_mode}'. "
            "Fix: use scd_mode='scd1' or scd_mode='scd2', or omit scd_mode."
        )

    has_scd_fields = any(
        [
            t.scd_tracked_columns is not None,
            t.scd_active_from_column is not None,
            t.scd_active_to_column is not None,
            t.business_key_static_columns is not None,
            t.business_key_changing_columns is not None,
        ]
    )
    if scd_mode is None and has_scd_fields:
        raise ValueError(
            f"Table '{t.table_name}': SCD fields provided without scd_mode. "
            "Fix: set scd_mode='scd1' or scd_mode='scd2', or remove SCD fields."
        )

    if scd_mode is not None:
        if not business_key:
            raise ValueError(
                f"Table '{t.table_name}': scd_mode='{scd_mode}' requires business_key. "
                "Fix: define business_key columns before enabling SCD."
            )
        if business_key_changing_columns and t.scd_tracked_columns:
            if set(business_key_changing_columns) != set(t.scd_tracked_columns):
                raise ValueError(
                    f"Table '{t.table_name}': business_key_changing_columns must match scd_tracked_columns when both are provided. "
                    "Fix: use the same column set in both fields, or leave scd_tracked_columns empty."
                )
        tracked = business_key_changing_columns or t.scd_tracked_columns or []
        if len(tracked) == 0:
            raise ValueError(
                f"Table '{t.table_name}': scd_mode='{scd_mode}' requires non-empty business_key_changing_columns or scd_tracked_columns. "
                "Fix: provide one or more existing column names for changing attributes."
            )
        for name in tracked:
            if name not in col_map:
                raise ValueError(
                    f"Table '{t.table_name}': changing columns include unknown column '{name}'. "
                    "Fix: use existing column names in business_key_changing_columns or scd_tracked_columns."
                )
            if business_key and name in business_key:
                raise ValueError(
                    f"Table '{t.table_name}', column '{name}': business_key columns cannot be tracked as changing. "
                    "Fix: track non-business-key columns for SCD changes."
                )

        if scd_mode == "scd1" and business_key_unique_count is not None and t.row_count > 0:
            if business_key_unique_count != t.row_count:
                raise ValueError(
                    f"Table '{t.table_name}': scd_mode='scd1' requires one row per business key, so business_key_unique_count ({business_key_unique_count}) must equal row_count ({t.row_count}). "
                    "Fix: set business_key_unique_count equal to row_count for SCD1 tables."
                )

        if scd_mode == "scd2":
            start_col = t.scd_active_from_column
            end_col = t.scd_active_to_column
            if not start_col or not end_col:
                raise ValueError(
                    f"Table '{t.table_name}': scd_mode='scd2' requires scd_active_from_column and scd_active_to_column. "
                    "Fix: set both columns to existing date or datetime columns."
                )
            if start_col not in col_map or end_col not in col_map:
                raise ValueError(
                    f"Table '{t.table_name}': SCD2 active period columns not found. "
                    "Fix: set scd_active_from_column/scd_active_to_column to existing columns."
                )
            start_dtype = col_map[start_col].dtype
            end_dtype = col_map[end_col].dtype
            if start_dtype not in {"date", "datetime"} or end_dtype not in {"date", "datetime"}:
                raise ValueError(
                    f"Table '{t.table_name}': SCD2 active period columns must be dtype date or datetime. "
                    "Fix: use date/datetime columns for scd_active_from_column and scd_active_to_column."
                )
            if start_dtype != end_dtype:
                raise ValueError(
                    f"Table '{t.table_name}': SCD2 active period column dtypes must match. "
                    "Fix: use the same dtype for scd_active_from_column and scd_active_to_column."
                )
        elif scd_mode == "scd1":
            start_col = t.scd_active_from_column
            end_col = t.scd_active_to_column
            if start_col or end_col:
                if not start_col or not end_col:
                    raise ValueError(
                        f"Table '{t.table_name}': SCD1 active period columns must be configured together. "
                        "Fix: set both scd_active_from_column and scd_active_to_column, or omit both."
                    )
                if start_col not in col_map or end_col not in col_map:
                    raise ValueError(
                        f"Table '{t.table_name}': SCD1 active period columns not found. "
                        "Fix: set scd_active_from_column/scd_active_to_column to existing columns."
                    )
                start_dtype = col_map[start_col].dtype
                end_dtype = col_map[end_col].dtype
                if start_dtype not in {"date", "datetime"} or end_dtype not in {"date", "datetime"}:
                    raise ValueError(
                        f"Table '{t.table_name}': SCD1 active period columns must be dtype date or datetime. "
                        "Fix: use date/datetime columns for scd_active_from_column and scd_active_to_column."
                    )
                if start_dtype != end_dtype:
                    raise ValueError(
                        f"Table '{t.table_name}': SCD1 active period column dtypes must match. "
                        "Fix: use the same dtype for scd_active_from_column and scd_active_to_column."
                    )


__all__ = ["validate_table_scd_and_business_key"]
