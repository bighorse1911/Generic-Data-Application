import unittest
import tempfile
import os
import sqlite3

from src.schema_project_model import SchemaProject, TableSpec, ColumnSpec, ForeignKeySpec
from src.storage_sqlite_project import create_tables, insert_project_rows


class TestSchemaProjectSQLiteFK(unittest.TestCase):
    def test_fk_enforced_in_sqlite(self):
        project = SchemaProject(
            name="sqlite-fk",
            seed=1,
            tables=[
                TableSpec(
                    table_name="customers",
                    row_count=2,
                    columns=[
                        ColumnSpec("customer_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("name", "text", nullable=False),
                    ],
                ),
                TableSpec(
                    table_name="orders",
                    columns=[
                        ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("customer_id", "int", nullable=False),
                    ],
                ),
            ],
            foreign_keys=[
                ForeignKeySpec("orders", "customer_id", "customers", "customer_id", 1, 1),
            ],
        )

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = tmp.name
        tmp.close()

        try:
            create_tables(db_path, project)

            # Insert a bad order referencing a non-existent customer_id
            bad_rows = {
                "customers": [
                    {"customer_id": 1, "name": "a"},
                ],
                "orders": [
                    {"order_id": 1, "customer_id": 9999},  # invalid FK
                ],
            }

            with self.assertRaises(sqlite3.IntegrityError):
                insert_project_rows(db_path, project, bad_rows, chunk_size=1000)

        finally:
            try:
                os.remove(db_path)
            except PermissionError:
                pass


if __name__ == "__main__":
    unittest.main()
