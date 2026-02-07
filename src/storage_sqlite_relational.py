import logging
import sqlite3
from typing import Iterable

from src.generator_relational import CustomerRow, OrderRow, OrderItemRow

logger = logging.getLogger("storage_sqlite_relational")


CREATE_CUSTOMERS_SQL = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

CREATE_ORDERS_SQL = """
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    order_date TEXT NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
);
"""

CREATE_ORDER_ITEMS_SQL = """
CREATE TABLE IF NOT EXISTS order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    FOREIGN KEY(order_id) REFERENCES orders(order_id)
);
"""

INSERT_CUSTOMERS_SQL = """
INSERT OR REPLACE INTO customers (customer_id, full_name, email, created_at)
VALUES (?, ?, ?, ?);
"""

INSERT_ORDERS_SQL = """
INSERT OR REPLACE INTO orders (order_id, customer_id, order_date, status)
VALUES (?, ?, ?, ?);
"""

INSERT_ORDER_ITEMS_SQL = """
INSERT OR REPLACE INTO order_items (order_item_id, order_id, sku, quantity, unit_price)
VALUES (?, ?, ?, ?, ?);
"""


def _connect(db_path: str) -> sqlite3.Connection:
    """
    Create a connection with foreign keys enforced.
    In SQLite, foreign key enforcement is OFF by default.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_relational_db(db_path: str) -> None:
    with _connect(db_path) as conn:
        conn.execute(CREATE_CUSTOMERS_SQL)
        conn.execute(CREATE_ORDERS_SQL)
        conn.execute(CREATE_ORDER_ITEMS_SQL)
        conn.commit()

    logger.info("Initialized relational schema at %s", db_path)


def insert_customers(db_path: str, rows: Iterable[CustomerRow]) -> int:
    rows_list = list(rows)
    with _connect(db_path) as conn:
        conn.executemany(
            INSERT_CUSTOMERS_SQL,
            [(r.customer_id, r.full_name, r.email, r.created_at) for r in rows_list],
        )
        conn.commit()
    logger.info("Inserted %d customers", len(rows_list))
    return len(rows_list)


def insert_orders(db_path: str, rows: Iterable[OrderRow]) -> int:
    rows_list = list(rows)
    with _connect(db_path) as conn:
        conn.executemany(
            INSERT_ORDERS_SQL,
            [(r.order_id, r.customer_id, r.order_date, r.status) for r in rows_list],
        )
        conn.commit()
    logger.info("Inserted %d orders", len(rows_list))
    return len(rows_list)


def insert_order_items(db_path: str, rows: Iterable[OrderItemRow]) -> int:
    rows_list = list(rows)
    with _connect(db_path) as conn:
        conn.executemany(
            INSERT_ORDER_ITEMS_SQL,
            [(r.order_item_id, r.order_id, r.sku, r.quantity, r.unit_price) for r in rows_list],
        )
        conn.commit()
    logger.info("Inserted %d order_items", len(rows_list))
    return len(rows_list)
