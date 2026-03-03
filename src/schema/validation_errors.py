"""Schema validation error formatting helpers."""

from src.schema.validators.common import _validation_error


def validation_error(location: str, issue: str, hint: str) -> str:
    return _validation_error(location, issue, hint)


__all__ = ["validation_error"]
