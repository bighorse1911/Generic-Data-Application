import hashlib
import logging
import random
import re
from datetime import date, datetime, timedelta, timezone

from src.schema_project_model import SchemaProject, TableSpec, ColumnSpec, ForeignKeySpec, validate_project

logger = logging.getLogger("generator_project")


def _stable_subseed(base_seed: int, name: str) -> int:
    """
    Deterministically derive a per-table/per-feature seed from base_seed and a string name.
    Avoids Python's built-in hash() which is randomized between runs.
    """
    h = hashlib.sha256(f"{base_seed}:{name}".encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _iso_date(d: date) -> str:
    return d.isoformat()


def _iso_datetime(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _gen_value(col: ColumnSpec, rng: random.Random, row_index: int) -> object:
    # Null handling
    if col.nullable and rng.random() < 0.05:  # 5% nulls
        return None

    # Primary key: deterministic increasing integer (1..N)
    if col.primary_key:
        return row_index

    # Choices override
    if col.choices is not None:
        return rng.choice(col.choices)

    if col.dtype == "int":
        lo = int(col.min_value) if col.min_value is not None else 0
        hi = int(col.max_value) if col.max_value is not None else 1000
        return rng.randint(lo, hi)

    if col.dtype == "float":
        lo = float(col.min_value) if col.min_value is not None else 0.0
        hi = float(col.max_value) if col.max_value is not None else 1000.0
        return round(rng.uniform(lo, hi), 2)

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

    if col.dtype == "text":
        pattern = re.compile(col.pattern) if col.pattern else None
        letters = "abcdefghijklmnopqrstuvwxyz"

        def candidate() -> str:
            length = rng.randint(5, 14)
            return "".join(rng.choice(letters) for _ in range(length))

        for _ in range(50):
            s = candidate()
            if pattern is None or pattern.fullmatch(s):
                return s
        return candidate()

    raise ValueError(f"Unsupported dtype: {col.dtype}")


def _dependency_order(project: SchemaProject) -> list[str]:
    """
    Return table names in parent->child order using Kahn's algorithm.
    MVP guarantees <=1 FK per child, but algorithm works regardless.
    """
    table_names = [t.table_name for t in project.tables]
    deps = {t: set() for t in table_names}       # t depends on these
    rev = {t: set() for t in table_names}        # these depend on t

    for fk in project.foreign_keys:
        child = fk.child_table
        parent = fk.parent_table
        deps[child].add(parent)
        rev[parent].add(child)

    # Kahn
    ready = [t for t in table_names if len(deps[t]) == 0]
    ready.sort()
    out = []

    while ready:
        n = ready.pop(0)
        out.append(n)
        for child in sorted(rev[n]):
            deps[child].discard(n)
            if len(deps[child]) == 0:
                ready.append(child)
                ready.sort()

    if len(out) != len(table_names):
        raise ValueError("Cycle detected in foreign key relationships (not supported).")

    return out


def generate_project_rows(project: SchemaProject) -> dict[str, list[dict[str, object]]]:
    """
    Generates rows for all tables with valid PK/FK according to the project's foreign key rules.

    Returns: dict of table_name -> list of row dicts
    """
    validate_project(project)

    table_map: dict[str, TableSpec] = {t.table_name: t for t in project.tables}
    fk_by_child: dict[str, ForeignKeySpec] = {fk.child_table: fk for fk in project.foreign_keys}

    order = _dependency_order(project)

    results: dict[str, list[dict[str, object]]] = {}
    pk_values: dict[str, list[int]] = {}  # table -> list of PK values

    # Helper: find PK column name for a table
    def pk_col_name(table: TableSpec) -> str:
        return [c.name for c in table.columns if c.primary_key][0]

    for table_name in order:
        t = table_map[table_name]
        rng = random.Random(_stable_subseed(project.seed, f"table:{table_name}"))

        pk_col = pk_col_name(t)

        # Determine row count
        if table_name not in fk_by_child:
            # root table
            n = t.row_count
            rows: list[dict[str, object]] = []
            for i in range(1, n + 1):
                row: dict[str, object] = {}
                for col in t.columns:
                    row[col.name] = _gen_value(col, rng, i)
                rows.append(row)
            results[table_name] = rows

            for r in rows:
                if r.get(pk_col) is None:
                    raise ValueError(f"PK is None in table={table_name}, pk_col={pk_col}. Check schema PK settings.")

            # Ensure PK column is always populated (defensive)
            for i, r in enumerate(rows, start=1):
                if r.get(pk_col) is None:
                    r[pk_col] = i

            pk_values[table_name] = [int(r.get(pk_col)) for r in rows]
            logger.info("Generated root table '%s' rows=%d", table_name, n)
        else:
            # child table: generate based on parent cardinality
            fk = fk_by_child[table_name]
            parent_table_name = fk.parent_table
            parent_ids = pk_values[parent_table_name]

            rows = []
            next_pk = 1

            # For each parent id, generate k child rows
            for pid in parent_ids:
                k = rng.randint(fk.min_children, fk.max_children)
                for _ in range(k):
                    row: dict[str, object] = {}
                    for col in t.columns:
                        if col.name == fk.child_column:
                            row[col.name] = pid  # FK value
                        else:
                            row[col.name] = _gen_value(col, rng, next_pk)
                    rows.append(row)
                    next_pk += 1

            results[table_name] = rows
            pk_values[table_name] = [int(r[pk_col]) for r in rows]
            logger.info(
                "Generated child table '%s' rows=%d (parent=%s rows=%d, per-parent=%d..%d)",
                table_name, len(rows), parent_table_name, len(parent_ids), fk.min_children, fk.max_children
            )

    return results
