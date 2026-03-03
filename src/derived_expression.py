"""Compatibility facade for the derived-expression engine."""

from __future__ import annotations

from typing import Any, Mapping

from src.derived_expression_common import _expression_error, _is_number, _is_scalar_literal
from src.derived_expression_compile import compile_derived_expression, extract_derived_expression_references
from src.derived_expression_datetime import is_iso_date_text, is_iso_datetime_text
from src.derived_expression_evaluator import _ExpressionEvaluator
from src.derived_expression_types import (
    MAX_EXPRESSION_DEPTH,
    MAX_EXPRESSION_LENGTH,
    MAX_EXPRESSION_NODES,
    CompiledDerivedExpression,
)
from src.derived_expression_validator import _ExpressionValidator


def evaluate_derived_expression(
    compiled: CompiledDerivedExpression,
    *,
    row: Mapping[str, Any],
    location: str,
) -> Any:
    evaluator = _ExpressionEvaluator(row=row, location=location)
    return evaluator.evaluate(compiled.body)


__all__ = [
    "MAX_EXPRESSION_LENGTH",
    "MAX_EXPRESSION_NODES",
    "MAX_EXPRESSION_DEPTH",
    "CompiledDerivedExpression",
    "compile_derived_expression",
    "extract_derived_expression_references",
    "evaluate_derived_expression",
    "is_iso_date_text",
    "is_iso_datetime_text",
    "_ExpressionValidator",
    "_ExpressionEvaluator",
    "_expression_error",
    "_is_scalar_literal",
    "_is_number",
]

