import csv
from pathlib import Path
from typing import Dict, List, Tuple

_CACHE: Dict[Tuple[str, int], List[str]] = {}
_MATCH_CACHE: Dict[Tuple[str, int, int], Dict[str, List[str]]] = {}

def load_csv_column(path: str, column_index: int, *, skip_header: bool = True) -> List[str]:
    key = (path, column_index)
    if key in _CACHE:
        return _CACHE[key]

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    values: List[str] = []
    with p.open("r", newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        if skip_header:
            next(r, None)
        for row in r:
            if column_index < len(row):
                v = row[column_index].strip()
                if v:
                    values.append(v)

    if not values:
        raise ValueError(f"No values loaded from CSV {path} column {column_index}")

    _CACHE[key] = values
    return values


def load_csv_column_by_match(
    path: str,
    column_index: int,
    match_column_index: int,
    *,
    skip_header: bool = True,
) -> Dict[str, List[str]]:
    key = (path, column_index, match_column_index)
    if key in _MATCH_CACHE:
        return _MATCH_CACHE[key]

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    values_by_match: Dict[str, List[str]] = {}
    with p.open("r", newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        if skip_header:
            next(r, None)
        for row in r:
            if column_index >= len(row) or match_column_index >= len(row):
                continue
            value = row[column_index].strip()
            if value == "":
                continue
            match_value = row[match_column_index].strip()
            values_by_match.setdefault(match_value, []).append(value)

    if not values_by_match:
        raise ValueError(
            f"No values loaded from CSV {path} with column_index={column_index} and match_column_index={match_column_index}"
        )

    _MATCH_CACHE[key] = values_by_match
    return values_by_match

