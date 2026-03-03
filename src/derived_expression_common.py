from __future__ import annotations


def _expression_error(location: str, issue: str, hint: str) -> str:
    return f"{location}: {issue}. Fix: {hint}."


def _is_scalar_literal(value: object) -> bool:
    return isinstance(value, (int, float, str, bool)) or value is None


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


