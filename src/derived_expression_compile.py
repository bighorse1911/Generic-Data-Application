from __future__ import annotations

import ast

from src.derived_expression_common import _expression_error
from src.derived_expression_types import (
    MAX_EXPRESSION_LENGTH,
    MAX_EXPRESSION_NODES,
    CompiledDerivedExpression,
)
from src.derived_expression_validator import _ExpressionValidator


def compile_derived_expression(
    expression: str,
    *,
    location: str,
) -> CompiledDerivedExpression:
    if not isinstance(expression, str) or expression.strip() == "":
        raise ValueError(
            _expression_error(
                location,
                "params.expression is required",
                "set params.expression to a non-empty expression string",
            )
        )
    trimmed = expression.strip()
    if len(trimmed) > MAX_EXPRESSION_LENGTH:
        raise ValueError(
            _expression_error(
                location,
                f"expression length exceeds {MAX_EXPRESSION_LENGTH} characters",
                "shorten the expression or split logic across multiple derived columns",
            )
        )

    try:
        parsed = ast.parse(trimmed, mode="eval")
    except SyntaxError as exc:
        detail = f"line {exc.lineno}, column {exc.offset}" if exc.lineno and exc.offset else "syntax error"
        raise ValueError(
            _expression_error(
                location,
                f"expression syntax is invalid ({detail})",
                "use a valid expression with allowed operators/functions",
            )
        ) from exc

    node_count = sum(1 for _ in ast.walk(parsed))
    if node_count > MAX_EXPRESSION_NODES:
        raise ValueError(
            _expression_error(
                location,
                f"expression complexity exceeds {MAX_EXPRESSION_NODES} AST nodes",
                "simplify the expression into smaller steps",
            )
        )

    validator = _ExpressionValidator(location=location)
    validator.validate(parsed.body, depth=1)

    return CompiledDerivedExpression(
        expression=trimmed,
        body=parsed.body,
        references=tuple(sorted(validator.references)),
    )


def extract_derived_expression_references(
    expression: str,
    *,
    location: str,
) -> tuple[str, ...]:
    compiled = compile_derived_expression(expression, location=location)
    return compiled.references

