from __future__ import annotations

from datetime import date, datetime


def is_iso_date_text(value: object) -> bool:
    if not isinstance(value, str) or value.strip() == "":
        return False
    try:
        date.fromisoformat(value.strip())
    except Exception:
        return False
    return True


def is_iso_datetime_text(value: object) -> bool:
    if not isinstance(value, str) or value.strip() == "":
        return False
    text = value.strip().replace("Z", "+00:00")
    try:
        datetime.fromisoformat(text)
    except Exception:
        return False
    return True

