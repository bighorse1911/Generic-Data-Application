from __future__ import annotations

import re

__all__ = [
    "ACTIONABLE_ERROR_PATTERN",
    "format_actionable_error",
    "is_actionable_message",
    "coerce_actionable_message",
]

ACTIONABLE_ERROR_PATTERN = re.compile(r"^[^:\n]+: .+\. Fix: .+\.$")


def _clean(value: object, default: str) -> str:
    text = str(value).strip()
    return text if text else default


def format_actionable_error(context: str, location: str, issue: str, hint: str) -> str:
    clean_context = str(context).strip()
    clean_location = _clean(location, "Unknown")
    clean_issue = _clean(issue, "unknown issue")
    clean_hint = _clean(hint, "review input and retry")
    if clean_context:
        return f"{clean_context} / {clean_location}: {clean_issue}. Fix: {clean_hint}."
    return f"{clean_location}: {clean_issue}. Fix: {clean_hint}."


def is_actionable_message(message: str) -> bool:
    return bool(ACTIONABLE_ERROR_PATTERN.match(str(message).strip()))


def coerce_actionable_message(
    context: str,
    raw_message: object,
    *,
    location: str,
    hint: str,
) -> str:
    text = str(raw_message).strip()
    if is_actionable_message(text):
        return text
    return format_actionable_error(
        context=context,
        location=location,
        issue=(text or "unknown issue"),
        hint=hint,
    )
