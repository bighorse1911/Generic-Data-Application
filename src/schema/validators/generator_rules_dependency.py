from __future__ import annotations

from src.derived_expression import compile_derived_expression
from src.project_paths import resolve_repo_path


def validate_dependency_generator_rules(table, column, *, col_map: dict[str, object]) -> None:
    if column.generator == "derived_expr":
        if column.dtype == "bytes":
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'derived_expr' does not support dtype bytes. "
                "Fix: use a non-bytes target dtype for derived expressions."
            )
        params = column.params or {}
        location = f"Table '{table.table_name}', column '{column.name}': generator 'derived_expr'"
        expression_raw = params.get("expression")
        if not isinstance(expression_raw, str) or expression_raw.strip() == "":
            raise ValueError(
                f"{location}: params.expression is required. "
                "Fix: set params.expression to a non-empty expression string."
            )
        try:
            compiled = compile_derived_expression(expression_raw, location=location)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        referenced_columns = list(compiled.references)
        for ref_name in referenced_columns:
            if ref_name == column.name:
                raise ValueError(
                    f"{location}: expression cannot reference the target column itself ('{column.name}'). "
                    "Fix: remove self references and derive from other source columns."
                )
            if ref_name not in col_map:
                raise ValueError(
                    f"{location}: expression reference '{ref_name}' was not found. "
                    "Fix: use existing source column names in params.expression."
                )

        depends_on = column.depends_on or []
        missing_depends = [ref_name for ref_name in referenced_columns if ref_name not in depends_on]
        if missing_depends:
            missing_display = ", ".join(missing_depends)
            raise ValueError(
                f"{location}: requires depends_on to include referenced expression columns ({missing_display}). "
                "Fix: add all expression source columns to depends_on so they generate first."
            )
    if column.generator == "sample_csv":
        params = column.params or {}
        path_value = params.get("path")
        if not isinstance(path_value, str) or path_value.strip() == "":
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'sample_csv' requires params.path. "
                "Fix: set params.path to a CSV file path."
            )
        path = path_value.strip()
        resolved_path = resolve_repo_path(path)
        if not resolved_path.exists():
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'sample_csv' params.path '{path}' does not exist. "
                "Fix: provide an existing CSV file path (for example tests/fixtures/city_country_pool.csv)."
            )
        col_idx_value = params.get("column_index", 0)
        try:
            col_idx = int(col_idx_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'sample_csv' params.column_index must be an integer. "
                "Fix: set params.column_index to 0 or greater."
            ) from exc
        if col_idx < 0:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'sample_csv' params.column_index cannot be negative. "
                "Fix: set params.column_index to 0 or greater."
            )
        match_col_raw = params.get("match_column")
        if match_col_raw is not None and not isinstance(match_col_raw, str):
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'sample_csv' params.match_column must be a string when provided. "
                "Fix: set params.match_column to an existing source column name or remove it."
            )

        match_col: str | None = None
        if isinstance(match_col_raw, str):
            stripped_match_col = match_col_raw.strip()
            if stripped_match_col != "":
                match_col = stripped_match_col

        match_col_idx_raw = params.get("match_column_index")
        if match_col is None:
            if match_col_idx_raw is not None:
                raise ValueError(
                    f"Table '{table.table_name}', column '{column.name}': generator 'sample_csv' params.match_column_index requires params.match_column. "
                    "Fix: set params.match_column to an existing source column name or remove params.match_column_index."
                )
        else:
            if match_col == column.name:
                raise ValueError(
                    f"Table '{table.table_name}', column '{column.name}': generator 'sample_csv' cannot reference itself in params.match_column. "
                    "Fix: choose a different source column name."
                )
            if match_col not in col_map:
                raise ValueError(
                    f"Table '{table.table_name}', column '{column.name}': generator 'sample_csv' params.match_column '{match_col}' was not found. "
                    "Fix: use an existing source column name."
                )
            depends_on = column.depends_on or []
            if match_col not in depends_on:
                raise ValueError(
                    f"Table '{table.table_name}', column '{column.name}': generator 'sample_csv' requires depends_on to include '{match_col}' when params.match_column is set. "
                    "Fix: add the source column to depends_on so it generates first."
                )
            if match_col_idx_raw is None:
                raise ValueError(
                    f"Table '{table.table_name}', column '{column.name}': generator 'sample_csv' requires params.match_column_index when params.match_column is set. "
                    "Fix: set params.match_column_index to the CSV column index that matches params.match_column."
                )
            try:
                match_col_idx = int(match_col_idx_raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Table '{table.table_name}', column '{column.name}': generator 'sample_csv' params.match_column_index must be an integer. "
                    "Fix: set params.match_column_index to 0 or greater."
                ) from exc
            if match_col_idx < 0:
                raise ValueError(
                    f"Table '{table.table_name}', column '{column.name}': generator 'sample_csv' params.match_column_index cannot be negative. "
                    "Fix: set params.match_column_index to 0 or greater."
                )
    if column.generator == "if_then":
        params = column.params or {}
        if_col = params.get("if_column")
        if not isinstance(if_col, str) or if_col.strip() == "":
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'if_then' requires params.if_column. "
                "Fix: set params.if_column to an existing source column name."
            )
        if_col = if_col.strip()
        if if_col == column.name:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'if_then' cannot reference itself in params.if_column. "
                "Fix: choose a different source column name."
            )
        if if_col not in col_map:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'if_then' params.if_column '{if_col}' was not found. "
                "Fix: use an existing source column name."
            )

        depends_on = column.depends_on or []
        if if_col not in depends_on:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'if_then' requires depends_on to include '{if_col}'. "
                "Fix: add the source column to depends_on so it generates first."
            )

        op = params.get("operator", "==")
        if not isinstance(op, str) or op not in {"==", "!="}:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'if_then' has unsupported operator '{op}'. "
                "Fix: use operator '==' or '!='."
            )
        if "value" not in params:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'if_then' requires params.value. "
                "Fix: set params.value to a comparison value."
            )
        if "then_value" not in params or "else_value" not in params:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'if_then' requires params.then_value and params.else_value. "
                "Fix: set both output values for true/false branches."
            )
        for key in ("value", "then_value", "else_value"):
            val = params.get(key)
            if isinstance(val, (dict, list)):
                raise ValueError(
                    f"Table '{table.table_name}', column '{column.name}': generator 'if_then' params.{key} must be a scalar value. "
                    "Fix: use string/number/bool/null values for if_then params."
                )
    if column.generator == "time_offset":
        params = column.params or {}
        if column.dtype not in {"date", "datetime"}:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'time_offset' requires dtype date or datetime. "
                "Fix: set column dtype to 'date' or 'datetime'."
            )
        base_col = params.get("base_column")
        if not isinstance(base_col, str) or base_col.strip() == "":
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'time_offset' requires params.base_column. "
                "Fix: set params.base_column to an existing source date/datetime column name."
            )
        base_col = base_col.strip()
        if base_col == column.name:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'time_offset' cannot reference itself in params.base_column. "
                "Fix: choose a different source column name."
            )
        if base_col not in col_map:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'time_offset' params.base_column '{base_col}' was not found. "
                "Fix: use an existing source column name."
            )
        base_dtype = col_map[base_col].dtype
        if base_dtype != column.dtype:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'time_offset' requires source and target dtypes to match (source '{base_dtype}', target '{column.dtype}'). "
                "Fix: use matching date/date or datetime/datetime columns."
            )
        depends_on = column.depends_on or []
        if base_col not in depends_on:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'time_offset' requires depends_on to include '{base_col}'. "
                "Fix: add the source column to depends_on so it generates first."
            )
        direction = params.get("direction", "after")
        if not isinstance(direction, str) or direction not in {"after", "before"}:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'time_offset' has unsupported direction '{direction}'. "
                "Fix: use direction 'after' or 'before'."
            )

        if column.dtype == "date":
            min_key = "min_days"
            max_key = "max_days"
            wrong_min_key = "min_seconds"
            wrong_max_key = "max_seconds"
            unit_hint = "day"
        else:
            min_key = "min_seconds"
            max_key = "max_seconds"
            wrong_min_key = "min_days"
            wrong_max_key = "max_days"
            unit_hint = "second"

        if wrong_min_key in params or wrong_max_key in params:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'time_offset' has unsupported offset keys for dtype '{column.dtype}'. "
                f"Fix: use params.{min_key} and params.{max_key} for this dtype."
            )

        min_raw = params.get(min_key, 0)
        max_raw = params.get(max_key, min_raw)
        try:
            min_offset = int(min_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'time_offset' params.{min_key} must be an integer. "
                f"Fix: set params.{min_key} to a whole-number {unit_hint} offset."
            ) from exc
        try:
            max_offset = int(max_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'time_offset' params.{max_key} must be an integer. "
                f"Fix: set params.{max_key} to a whole-number {unit_hint} offset."
            ) from exc
        if min_offset < 0 or max_offset < 0:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'time_offset' offsets must be non-negative. "
                "Fix: set min/max offsets to 0 or greater."
            )
        if min_offset > max_offset:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'time_offset' min offset cannot exceed max offset. "
                "Fix: set min offset <= max offset."
            )
    if column.generator == "hierarchical_category":
        params = column.params or {}
        if column.dtype != "text":
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'hierarchical_category' requires dtype text. "
                "Fix: set column dtype to 'text'."
            )
        parent_col = params.get("parent_column")
        if not isinstance(parent_col, str) or parent_col.strip() == "":
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'hierarchical_category' requires params.parent_column. "
                "Fix: set params.parent_column to an existing source category column name."
            )
        parent_col = parent_col.strip()
        if parent_col == column.name:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'hierarchical_category' cannot reference itself in params.parent_column. "
                "Fix: choose a different source column name."
            )
        if parent_col not in col_map:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'hierarchical_category' params.parent_column '{parent_col}' was not found. "
                "Fix: use an existing source column name."
            )
        depends_on = column.depends_on or []
        if parent_col not in depends_on:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'hierarchical_category' requires depends_on to include '{parent_col}'. "
                "Fix: add the source column to depends_on so it generates first."
            )
        hierarchy = params.get("hierarchy")
        if not isinstance(hierarchy, dict) or not hierarchy:
            raise ValueError(
                f"Table '{table.table_name}', column '{column.name}': generator 'hierarchical_category' requires a non-empty params.hierarchy object. "
                "Fix: set params.hierarchy to a mapping like {'Parent': ['ChildA', 'ChildB']}."
            )
        for parent_value, children in hierarchy.items():
            if not isinstance(children, list) or len(children) == 0:
                raise ValueError(
                    f"Table '{table.table_name}', column '{column.name}': generator 'hierarchical_category' parent '{parent_value}' must map to a non-empty child list. "
                    "Fix: configure one or more child values per parent in params.hierarchy."
                )
            for child_value in children:
                if isinstance(child_value, (dict, list)):
                    raise ValueError(
                        f"Table '{table.table_name}', column '{column.name}': generator 'hierarchical_category' child values must be scalar. "
                        "Fix: use string/number/bool/null values in child lists."
                    )
        default_children = params.get("default_children")
        if default_children is not None:
            if not isinstance(default_children, list) or len(default_children) == 0:
                raise ValueError(
                    f"Table '{table.table_name}', column '{column.name}': generator 'hierarchical_category' params.default_children must be a non-empty list when provided. "
                    "Fix: set params.default_children to one or more fallback child values or omit it."
                )
            for child_value in default_children:
                if isinstance(child_value, (dict, list)):
                    raise ValueError(
                        f"Table '{table.table_name}', column '{column.name}': generator 'hierarchical_category' params.default_children values must be scalar. "
                        "Fix: use string/number/bool/null values in params.default_children."
                    )
        parent_choices = col_map[parent_col].choices or []
        if parent_choices and default_children is None:
            missing = [
                choice
                for choice in parent_choices
                if choice not in hierarchy and str(choice) not in hierarchy
            ]
            if missing:
                missing_display = ", ".join(str(x) for x in missing)
                raise ValueError(
                    f"Table '{table.table_name}', column '{column.name}': generator 'hierarchical_category' is missing hierarchy entries for parent choices ({missing_display}). "
                    "Fix: add those choices to params.hierarchy or set params.default_children."
                )

__all__ = ["validate_dependency_generator_rules"]
