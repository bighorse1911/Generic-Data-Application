import csv
from pathlib import Path
from typing import Dict, List, Tuple

_CACHE: Dict[Tuple[str, int], List[str]] = {}

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

