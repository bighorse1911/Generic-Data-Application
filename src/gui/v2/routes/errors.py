from __future__ import annotations


def _v2_error(location: str, issue: str, hint: str) -> str:
    return f"Run Center v2 / {location}: {issue}. Fix: {hint}."


__all__ = ["_v2_error"]
