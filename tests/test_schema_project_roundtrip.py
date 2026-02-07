import unittest
import tempfile
import os

from src.schema_project_model import (
    SchemaProject, TableSpec, ColumnSpec, ForeignKeySpec
)
from src.schema_project_io import save_project_to_json, load_project_from_json


class TestSchemaProjectRoundtrip(unittest.TestCase):
    def test_roundtrip_json(self):
        project = SchemaProject(
            name="demo",
            seed=7,
            tables=[
                TableSpec(
                    table_name="customers",
                    row_count=3,
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
                        ColumnSpec("status", "text", nullable=False, choices=["NEW", "PAID"]),
                    ],
                ),
            ],
            foreign_keys=[
                ForeignKeySpec(
                    child_table="orders",
                    child_column="customer_id",
                    parent_table="customers",
                    parent_column="customer_id",
                    min_children=1,
                    max_children=2,
                )
            ],
        )

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        path = tmp.name
        tmp.close()

        try:
            save_project_to_json(project, path)
            loaded = load_project_from_json(path)
            self.assertEqual(project, loaded)
        finally:
            try:
                os.remove(path)
            except PermissionError:
                pass


if __name__ == "__main__":
    unittest.main()
