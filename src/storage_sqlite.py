import logging
import sqlite3
from typing import Iterable

from src.generator import PersonRow

logger = logging.getLogger("storage_sqlite")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS people (
    person_id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL,
    age INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
"""

INSERT_SQL = """
INSERT OR REPLACE INTO people (person_id, first_name, last_name, email, age, created_at)
VALUES (?, ?, ?, ?, ?, ?);
"""

def init_db(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()
    logger.info("Initialized SQLite DB at %s", db_path)

def insert_people(db_path: str, rows: Iterable[PersonRow]) -> int:
    rows_list = list(rows)
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            INSERT_SQL,
            [
                (r.person_id, r.first_name, r.last_name, r.email, r.age, r.created_at)
                for r in rows_list
            ],
        )
        conn.commit()

    logger.info("Inserted %d rows into %s", len(rows_list), db_path)
    return len(rows_list)
