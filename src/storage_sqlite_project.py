import logging
import sqlite3
from typing import Iterable

from src.schema_project_model import SchemaProject, TableSpec, ColumnSpec, ForeignKeySpec, validate_project
from src.generator_project import _dependency_order  # internal helper

logger = logging.getLogger("storage_sqlite_project")


def _sqlite_type(dtype: str) -> str:
    return {
        "int": "INTEGER",
        "decimal": "REAL",
        "float": "REAL",
        "text": "TEXT",
        "bool": "INTEGER",
        "date": "TEXT",
        "datetime": "TEXT",
    }[dtype]


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def create_tables(db_path: str, project: SchemaProject) -> None:
    validate_project(project)

    table_map = {t.table_name: t for t in project.tables}

    # group FKs by child table
    fks_by_child: dict[str, list[ForeignKeySpec]] = {}
    for fk in project.foreign_keys:
        fks_by_child.setdefault(fk.child_table, []).append(fk)

    with _connect(db_path) as conn:
        for t in project.tables:
            col_defs = []
            for c in t.columns:
                parts = [c.name, _sqlite_type(c.dtype)]
                if not c.nullable:
                    parts.append("NOT NULL")
                if c.primary_key:
                    parts.append("PRIMARY KEY")
                if c.unique and not c.primary_key:
                    parts.append("UNIQUE")
                col_defs.append(" ".join(parts))

            # FK clauses (SQLite wants them inside CREATE TABLE)
            fk_clauses = []
            for fk in fks_by_child.get(t.table_name, []):
                fk_clauses.append(
                    f"FOREIGN KEY({fk.child_column}) REFERENCES {fk.parent_table}({fk.parent_column})"
                )

            all_defs = col_defs + fk_clauses
            sql = f"CREATE TABLE IF NOT EXISTS {t.table_name} (\n  " + ",\n  ".join(all_defs) + "\n);"
            conn.execute(sql)

        conn.commit()

    logger.info("Created tables for project '%s' in %s", project.name, db_path)


def insert_project_rows(
    db_path: str,
    project: SchemaProject,
    rows_by_table: dict[str, list[dict[str, object]]],
    chunk_size: int = 5000,
) -> dict[str, int]:
    """
    Insert rows in dependency order: parents first, then children.
    Returns: table_name -> inserted_count
    """
    validate_project(project)

    table_map = {t.table_name: t for t in project.tables}
    order = _dependency_order(project)

    inserted_counts: dict[str, int] = {}

    with _connect(db_path) as conn:
        conn.execute("BEGIN;")

        for table_name in order:
            t = table_map[table_name]
            rows = rows_by_table.get(table_name, [])
            if not rows:
                inserted_counts[table_name] = 0
                continue

            cols = [c.name for c in t.columns]
            placeholders = ", ".join(["?"] * len(cols))
            sql = f"INSERT INTO {table_name} ({', '.join(cols)}) VALUES ({placeholders});"

            total = 0
            batch: list[list[object]] = []

            for r in rows:
                batch.append([r.get(c) for c in cols])
                if len(batch) >= chunk_size:
                    conn.executemany(sql, batch)
                    total += len(batch)
                    batch = []
            if batch:
                conn.executemany(sql, batch)
                total += len(batch)

            inserted_counts[table_name] = total

        conn.commit()

    logger.info("Inserted project rows into %s: %s", db_path, inserted_counts)
    return inserted_counts
