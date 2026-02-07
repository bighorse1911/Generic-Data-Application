import logging
import sqlite3
from typing import Iterable

from src.generator_relational import CustomerRow, OrderRow, OrderItemRow, RelationalData

logger = logging.getLogger("storage_sqlite_relational")
CREATE_CUSTOMERS_SQL = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
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
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CHECK (status IN ('NEW', 'PAID', 'SHIPPED', 'CANCELLED'))
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
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CHECK (quantity > 0),
    CHECK (unit_price >= 0.0)
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
CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);",
    "CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);",
    "CREATE INDEX IF NOT EXISTS idx_order_items_sku ON order_items(sku);",
]


def _connect(db_path: str) -> sqlite3.Connection:
    """
    Create a connection with foreign keys enforced.
    In SQLite, foreign key enforcement is OFF by default.
    """
    conn = sqlite3.connect(db_path, timeout = 30)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_relational_db(db_path: str) -> None:
    with _connect(db_path) as conn:
        conn.execute(CREATE_CUSTOMERS_SQL)
        conn.execute(CREATE_ORDERS_SQL)
        conn.execute(CREATE_ORDER_ITEMS_SQL)

        for sql in CREATE_INDEXES_SQL:
            conn.execute(sql)

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

def insert_relational_data(db_path: str, data: RelationalData) -> tuple[int, int, int]:
    """
    Insert all tables in one transaction (fast + atomic).
    Returns (customers_count, orders_count, items_count).
    """
    customers = list(data.customers)
    orders = list(data.orders)
    items = list(data.order_items)

    with _connect(db_path) as conn:
        conn.execute("BEGIN;")

        conn.executemany(
            INSERT_CUSTOMERS_SQL,
            [(r.customer_id, r.full_name, r.email, r.created_at) for r in customers],
        )

        conn.executemany(
            INSERT_ORDERS_SQL,
            [(r.order_id, r.customer_id, r.order_date, r.status) for r in orders],
        )

        conn.executemany(
            INSERT_ORDER_ITEMS_SQL,
            [(r.order_item_id, r.order_id, r.sku, r.quantity, r.unit_price) for r in items],
        )

        conn.commit()

    logger.info("Inserted relational data: customers=%d orders=%d items=%d",
                len(customers), len(orders), len(items))
    return (len(customers), len(orders), len(items))

