from __future__ import annotations


def _replace_name_in_list(values: list[str] | None, *, old_name: str, new_name: str) -> list[str] | None:
    if values is None:
        return None
    return [new_name if value == old_name else value for value in values]


def _replace_name_in_optional_value(value: str | None, *, old_name: str, new_name: str) -> str | None:
    if value is None:
        return None
    return new_name if value == old_name else value


__all__ = [
    "_replace_name_in_list",
    "_replace_name_in_optional_value",
]
