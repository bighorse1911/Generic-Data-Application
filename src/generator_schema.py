import logging
import random
import re
from datetime import date, datetime, timedelta, timezone

from src.schema_model import TableSchema, ColumnSpec, validate_schema

logger = logging.getLogger("generator_schema")

def _iso_date(d: date) -> str:
    return d.isoformat()

def _iso_datetime(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")

def _gen_value(col: ColumnSpec, rng: random.Random, row_index: int, used_uniques: dict[str, set]) -> object:
    # Null handling
    if col.nullable and rng.random() < 0.05:  # 5% nulls
        return None

    # Primary key: deterministic increasing integer
    if col.primary_key:
        if col.dtype != "int":
            raise ValueError(f"Primary key column '{col.name}' must be dtype=int in this MVP.")
        return row_index  # 1..N

    # Choices override most other rules
    if col.choices is not None:
        v = rng.choice(col.choices)
        return v

    if col.dtype == "int":
        lo = int(col.min_value) if col.min_value is not None else 0
        hi = int(col.max_value) if col.max_value is not None else 1000
        v = rng.randint(lo, hi)
        return v

    if col.dtype == "float":
        lo = float(col.min_value) if col.min_value is not None else 0.0
        hi = float(col.max_value) if col.max_value is not None else 1000.0
        v = rng.uniform(lo, hi)
        return round(v, 2)

    if col.dtype == "bool":
        return 1 if rng.random() < 0.5 else 0

    if col.dtype == "date":
        base = date(2020, 1, 1)
        d = base + timedelta(days=rng.randint(0, 3650))
        return _iso_date(d)

    if col.dtype == "datetime":
        base = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=rng.randint(0, 10_000_000))
        dt = base - timedelta(seconds=rng.randint(0, 3600 * 24 * 30))
        return _iso_datetime(dt)

    # text
    if col.dtype == "text":
        # If pattern provided, we can't perfectly "generate from regex" in stdlib.
        # MVP strategy: generate candidates and test against regex with retries.
        pattern = re.compile(col.pattern) if col.pattern else None

        def candidate() -> str:
            # simple text generator
            length = rng.randint(5, 14)
            letters = "abcdefghijklmnopqrstuvwxyz"
            s = "".join(rng.choice(letters) for _ in range(length))
            return s

        for _ in range(50):
            s = candidate()
            if pattern is None or pattern.fullmatch(s):
                return s

        # fallback: return something even if pattern is too strict
        return candidate()

    raise ValueError(f"Unsupported dtype: {col.dtype}")

def generate_rows(schema: TableSchema, n: int) -> list[dict[str, object]]:
    validate_schema(schema)
    if n <= 0:
        raise ValueError("n must be > 0")

    rng = random.Random(schema.seed)
    used_uniques: dict[str, set] = {c.name: set() for c in schema.columns if c.unique}

    rows: list[dict[str, object]] = []
    for i in range(1, n + 1):
        row: dict[str, object] = {}
        for col in schema.columns:
            # Generate value
            v = _gen_value(col, rng, i, used_uniques)

            # Enforce uniqueness (basic)
            if col.unique and v is not None:
                # retry a few times if collision
                attempts = 0
                while v in used_uniques[col.name] and attempts < 50:
                    v = _gen_value(col, rng, i, used_uniques)
                    attempts += 1
                used_uniques[col.name].add(v)

            row[col.name] = v
        rows.append(row)

    logger.info("Generated %d rows for table '%s'", n, schema.table_name)
    return rows
