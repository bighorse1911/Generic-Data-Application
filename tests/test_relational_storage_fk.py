import unittest
import tempfile
import os
import sqlite3

from src.storage_sqlite_relational import init_relational_db, insert_orders
from src.generator_relational import OrderRow


class TestRelationalStorageFK(unittest.TestCase):
    def test_fk_enforced(self):
        # Create a temp file path that we can safely clean up on Windows.
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = tmp.name
        tmp.close()  # IMPORTANT: close the handle so SQLite can open it.

        try:
            init_relational_db(db_path)

            # Try inserting an order referencing a customer that doesn't exist.
            bad_order = OrderRow(
                order_id=1,
                customer_id=9999,
                order_date="2020-01-01T00:00:00Z",
                status="NEW",
            )

            with self.assertRaises(sqlite3.IntegrityError):
                insert_orders(db_path, [bad_order])

        finally:
            # Ensure DB file is removed even if the test fails.
            try:
                os.remove(db_path)
            except PermissionError:
                # Very occasionally Windows holds the lock a moment longer.
                # If this happens, the file will be cleaned up later by temp policies.
                pass


if __name__ == "__main__":
    unittest.main()
