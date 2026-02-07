import logging
import sqlite3
from typing import Iterable

from src.schema_model import TableSchema, ColumnSpec, validate_schema

logger = logging.getLogger("storage_sqlite_schema")

def _sqlite_type(dtype: str) -> str:
    return {
        "int": "INTEGER",
        "float": "REAL",
        "text": "TEXT",
        "bool": "INTEGER",
        "date": "TEXT",
        "datetime": "TEXT",
    }[dtype]

def create_table_from_schema(db_path: str, schema: TableSchema) -> None:
    validate_schema(schema)

    col_defs = []
    for c in schema.columns:
        parts = [c.name, _sqlite_type(c.dtype)]
        if not c.nullable:
            parts.append("NOT NULL")
        if c.primary_key:
            parts.append("PRIMARY KEY")
        if c.unique and not c.primary_key:
            parts.append("UNIQUE")
        col_defs.append(" ".join(parts))

    sql = f"CREATE TABLE IF NOT EXISTS {schema.table_name} (\n  " + ",\n  ".join(col_defs) + "\n);"

    with sqlite3.connect(db_path) as conn:
        conn.execute(sql)
        conn.commit()

    logger.info("Created table (if not exists): %s", schema.table_name)

def insert_rows(db_path: str, schema: TableSchema, rows: Iterable[dict[str, object]], chunk_size: int = 5000) -> int:
    validate_schema(schema)
    cols = [c.name for c in schema.columns]
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT INTO {schema.table_name} ({', '.join(cols)}) VALUES ({placeholders});"

    rows_list = list(rows)  # MVP: assumes rows are from preview; Option C will stream instead
    with sqlite3.connect(db_path) as conn:
        # speed for bigger inserts
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("BEGIN;")

        total = 0
        batch = []
        for r in rows_list:
            batch.append([r.get(c) for c in cols])
            if len(batch) >= chunk_size:
                conn.executemany(sql, batch)
                total += len(batch)
                batch = []
        if batch:
            conn.executemany(sql, batch)
            total += len(batch)

        conn.commit()

    logger.info("Inserted %d rows into %s", total, schema.table_name)
    return total
