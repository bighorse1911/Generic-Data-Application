from __future__ import annotations

from typing import Any, Dict

from src.derived_expression import compile_derived_expression
from src.derived_expression import evaluate_derived_expression
from src.derived_expression import is_iso_date_text
from src.derived_expression import is_iso_datetime_text
from src.generation.generator_common import _generator_error
from src.generation.generator_state import _DERIVED_EXPRESSION_STATE
from src.generation.registry_core import GenContext, register


def _coerce_derived_expression_result(value: Any, *, dtype: str, location: str) -> Any:
    target_dtype = dtype.strip().lower()
    if target_dtype == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(
                _generator_error(
                    location,
                    f"derived expression result type '{type(value).__name__}' is incompatible with dtype 'int'",
                    "return an integer result or cast explicitly with to_int(...)",
                )
            )
        return value
    if target_dtype in {"decimal", "float"}:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(
                _generator_error(
                    location,
                    f"derived expression result type '{type(value).__name__}' is incompatible with dtype '{target_dtype}'",
                    "return a numeric result or cast explicitly with to_decimal(...)",
                )
            )
        return float(value)
    if target_dtype == "text":
        if not isinstance(value, str):
            raise ValueError(
                _generator_error(
                    location,
                    f"derived expression result type '{type(value).__name__}' is incompatible with dtype 'text'",
                    "return text directly or cast explicitly with to_text(...)",
                )
            )
        return value
    if target_dtype == "bool":
        if not isinstance(value, bool):
            raise ValueError(
                _generator_error(
                    location,
                    f"derived expression result type '{type(value).__name__}' is incompatible with dtype 'bool'",
                    "return a boolean expression result or cast explicitly with to_bool(...)",
                )
            )
        return value
    if target_dtype == "date":
        if not is_iso_date_text(value):
            raise ValueError(
                _generator_error(
                    location,
                    "derived expression result is not a valid ISO date",
                    "return text in 'YYYY-MM-DD' format for date columns",
                )
            )
        return str(value).strip()
    if target_dtype == "datetime":
        if not is_iso_datetime_text(value):
            raise ValueError(
                _generator_error(
                    location,
                    "derived expression result is not a valid ISO datetime",
                    "return ISO datetime text (for example '2026-02-24T10:00:00Z')",
                )
            )
        return str(value).strip()
    return value


@register("derived_expr")
def gen_derived_expr(params: Dict[str, Any], ctx: GenContext) -> Any:
    location = f"Table '{ctx.table}', column '{ctx.column}', generator 'derived_expr'"
    expression_raw = params.get("expression")
    if not isinstance(expression_raw, str) or expression_raw.strip() == "":
        raise ValueError(
            _generator_error(
                location,
                "params.expression is required",
                "set params.expression to a non-empty expression string",
            )
        )
    expression = expression_raw.strip()

    column_key = ctx.column.strip() if isinstance(ctx.column, str) and ctx.column.strip() else f"params:{id(params)}"
    state_key = (ctx.table, column_key)
    compiled = _DERIVED_EXPRESSION_STATE.get(state_key)
    if compiled is None or compiled.expression != expression:
        compiled = compile_derived_expression(expression, location=location)
        _DERIVED_EXPRESSION_STATE[state_key] = compiled

    value = evaluate_derived_expression(compiled, row=ctx.row, location=location)
    return _coerce_derived_expression_result(value, dtype=ctx.dtype, location=location)


__all__ = ["gen_derived_expr"]
