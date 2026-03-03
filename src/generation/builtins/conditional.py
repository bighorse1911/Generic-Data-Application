from __future__ import annotations

from typing import Any, Dict

from src.generation.generator_common import _generator_error
from src.generation.registry_core import GenContext, register


@register("if_then")
def gen_if_then(params: Dict[str, Any], ctx: GenContext) -> Any:
    if_col = params.get("if_column")
    if not isinstance(if_col, str) or if_col.strip() == "":
        raise ValueError(
            _generator_error(
                f"Table '{ctx.table}', generator 'if_then'",
                "params.if_column is required",
                "set params.if_column to a source column name and add it to depends_on",
            )
        )
    if_col = if_col.strip()

    if if_col not in ctx.row:
        raise ValueError(
            _generator_error(
                f"Table '{ctx.table}', generator 'if_then'",
                f"if_column '{if_col}' is not available in row context",
                "set depends_on to include the source column so it generates first",
            )
        )

    op = params.get("operator", "==")
    if not isinstance(op, str) or op not in {"==", "!="}:
        raise ValueError(
            _generator_error(
                f"Table '{ctx.table}', generator 'if_then'",
                f"unsupported operator '{op}'",
                "use operator '==' or '!='",
            )
        )

    if "value" not in params:
        raise ValueError(
            _generator_error(
                f"Table '{ctx.table}', generator 'if_then'",
                "params.value is required",
                "set params.value to the comparison value",
            )
        )
    if "then_value" not in params or "else_value" not in params:
        raise ValueError(
            _generator_error(
                f"Table '{ctx.table}', generator 'if_then'",
                "params.then_value and params.else_value are required",
                "set both output values for true/false branches",
            )
        )

    left = ctx.row[if_col]
    right = params["value"]
    condition = left == right if op == "==" else left != right
    return params["then_value"] if condition else params["else_value"]


__all__ = ["gen_if_then"]
