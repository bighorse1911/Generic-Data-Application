import os
import tempfile
import unittest

from src.generator_project import generate_project_rows
from src.schema_project_io import build_project_sql_ddl
from src.schema_project_model import ColumnSpec, SchemaProject, TableSpec, validate_project
from src.storage_sqlite_project import create_tables, insert_project_rows


class TestDirection3Decimal(unittest.TestCase):
    def _decimal_project(self) -> SchemaProject:
        return SchemaProject(
            name="direction3_decimal",
            seed=123,
            tables=[
                TableSpec(
                    table_name="metrics",
                    row_count=6,
                    columns=[
                        ColumnSpec("metric_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("amount", "decimal", nullable=False, min_value=1.25, max_value=2.75),
                        ColumnSpec(
                            "latitude",
                            "decimal",
                            nullable=False,
                            generator="latitude",
                            params={"min": 37.0, "max": 38.0, "decimals": 4},
                        ),
                        ColumnSpec(
                            "budget",
                            "decimal",
                            nullable=False,
                            generator="money",
                            params={"min": 100.0, "max": 200.0, "decimals": 2},
                        ),
                        ColumnSpec(
                            "discount_pct",
                            "decimal",
                            nullable=False,
                            generator="percent",
                            params={"min": 0.0, "max": 15.0, "decimals": 1},
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )

    def test_decimal_generation_is_supported_and_deterministic(self):
        project = self._decimal_project()
        validate_project(project)

        rows_a = generate_project_rows(project)
        rows_b = generate_project_rows(project)
        self.assertEqual(rows_a, rows_b)

        for row in rows_a["metrics"]:
            self.assertIsInstance(row["amount"], float)
            self.assertGreaterEqual(row["amount"], 1.25)
            self.assertLessEqual(row["amount"], 2.75)

            self.assertGreaterEqual(row["latitude"], 37.0)
            self.assertLessEqual(row["latitude"], 38.0)

            self.assertGreaterEqual(row["budget"], 100.0)
            self.assertLessEqual(row["budget"], 200.0)

            self.assertGreaterEqual(row["discount_pct"], 0.0)
            self.assertLessEqual(row["discount_pct"], 15.0)

    def test_sql_and_sqlite_paths_support_decimal(self):
        project = self._decimal_project()
        ddl = build_project_sql_ddl(project)
        self.assertIn('"amount" DECIMAL NOT NULL', ddl)
        self.assertIn('"budget" DECIMAL NOT NULL', ddl)

        rows = generate_project_rows(project)

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = tmp.name
        tmp.close()
        try:
            create_tables(db_path, project)
            inserted = insert_project_rows(db_path, project, rows, chunk_size=500)
            self.assertEqual(inserted, {"metrics": 6})
        finally:
            try:
                os.remove(db_path)
            except PermissionError:
                pass

    def test_legacy_float_dtype_remains_supported(self):
        project = SchemaProject(
            name="legacy_float",
            seed=4,
            tables=[
                TableSpec(
                    table_name="legacy_metrics",
                    row_count=3,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec("score", "float", nullable=False, min_value=0.5, max_value=1.5),
                    ],
                )
            ],
            foreign_keys=[],
        )
        validate_project(project)
        rows = generate_project_rows(project)
        for row in rows["legacy_metrics"]:
            self.assertGreaterEqual(row["score"], 0.5)
            self.assertLessEqual(row["score"], 1.5)

    def test_semantic_numeric_dtype_error_has_fix_hint(self):
        bad = SchemaProject(
            name="bad_semantic_dtype",
            seed=1,
            tables=[
                TableSpec(
                    table_name="events",
                    row_count=2,
                    columns=[
                        ColumnSpec("event_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("event_lat", "latitude", nullable=False),
                    ],
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            validate_project(bad)

        msg = str(ctx.exception)
        self.assertIn("Table 'events'", msg)
        self.assertIn("column 'event_lat'", msg)
        self.assertIn("unsupported dtype 'latitude'", msg)
        self.assertIn("dtype='decimal' (or legacy 'float')", msg)
        self.assertIn("generator='latitude'", msg)


if __name__ == "__main__":
    unittest.main()
