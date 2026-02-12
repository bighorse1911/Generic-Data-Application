import unittest
import tempfile
import os
import json
from pathlib import Path

from src.schema_project_model import (
    SchemaProject, TableSpec, ColumnSpec, ForeignKeySpec
)
from src.schema_project_io import save_project_to_json, load_project_from_json, build_project_sql_ddl


class TestSchemaProjectRoundtrip(unittest.TestCase):
    def _project(self) -> SchemaProject:
        return SchemaProject(
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

    def test_roundtrip_json(self):
        project = self._project()

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

    def test_save_json_appends_sql_ddl_string(self):
        project = self._project()

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        path = tmp.name
        tmp.close()

        try:
            save_project_to_json(project, path)
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)

            self.assertIn("sql_ddl", raw)
            self.assertIsInstance(raw["sql_ddl"], str)
            self.assertEqual(raw["sql_ddl"], build_project_sql_ddl(project))
            self.assertIn('CREATE TABLE "customers"', raw["sql_ddl"])
            self.assertIn('CREATE TABLE "orders"', raw["sql_ddl"])
            self.assertIn(
                'FOREIGN KEY ("customer_id") REFERENCES "customers" ("customer_id")',
                raw["sql_ddl"],
            )
        finally:
            try:
                os.remove(path)
            except PermissionError:
                pass

    def test_load_rejects_non_string_sql_ddl_with_fix_hint(self):
        payload = {
            "name": "demo",
            "seed": 7,
            "tables": [
                {
                    "table_name": "customers",
                    "columns": [
                        {"name": "customer_id", "dtype": "int", "nullable": False, "primary_key": True},
                    ],
                }
            ],
            "foreign_keys": [],
            "sql_ddl": {"bad": "type"},
        }

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        path = tmp.name
        tmp.close()

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f)

            with self.assertRaises(ValueError) as ctx:
                load_project_from_json(path)

            msg = str(ctx.exception)
            self.assertIn("sql_ddl", msg)
            self.assertIn("must be a string", msg)
            self.assertIn("Fix:", msg)
        finally:
            try:
                os.remove(path)
            except PermissionError:
                pass

    def test_save_normalizes_sample_csv_path_to_repo_relative(self):
        fixture_csv = Path(__file__).resolve().parent / "fixtures" / "city_country_pool.csv"
        project = SchemaProject(
            name="csv_path_normalize",
            seed=12,
            tables=[
                TableSpec(
                    table_name="people",
                    row_count=2,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "city",
                            "text",
                            nullable=False,
                            generator="sample_csv",
                            params={"path": str(fixture_csv), "column_index": 0},
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        path = tmp.name
        tmp.close()

        try:
            save_project_to_json(project, path)
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)

            saved_path = raw["tables"][0]["columns"][1]["params"]["path"]
            self.assertEqual(saved_path, "tests/fixtures/city_country_pool.csv")
        finally:
            try:
                os.remove(path)
            except PermissionError:
                pass


if __name__ == "__main__":
    unittest.main()
