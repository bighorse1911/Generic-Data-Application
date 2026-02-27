import os
import tempfile
import unittest

from src.generator_project import generate_project_rows
from src.schema_project_model import ColumnSpec
from src.schema_project_model import SchemaProject
from src.schema_project_model import TableSpec
from src.schema_project_model import validate_project


class TestSampleProfileFitting(unittest.TestCase):
    def _write_csv(self, rows: list[list[str]]) -> str:
        tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", encoding="utf-8", newline="")
        try:
            for row in rows:
                tmp.write(",".join(row) + "\n")
            return tmp.name
        finally:
            tmp.close()

    def test_dg07_infers_profiles_from_csv_samples_deterministically(self) -> None:
        path = self._write_csv(
            [
                ["amount", "category", "ordered_on"],
                ["100.0", "A", "2025-01-01"],
                ["120.0", "B", "2025-01-02"],
                ["130.0", "B", "2025-01-04"],
                ["150.0", "C", "2025-01-05"],
            ]
        )
        try:
            project = SchemaProject(
                name="dg07_infer_profiles",
                seed=444,
                tables=[
                    TableSpec(
                        table_name="orders",
                        row_count=40,
                        columns=[
                            ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                            ColumnSpec("amount", "decimal", nullable=False),
                            ColumnSpec("category", "text", nullable=False),
                            ColumnSpec("ordered_on", "date", nullable=False),
                        ],
                    )
                ],
                foreign_keys=[],
                sample_profile_fits=[
                    {
                        "fit_id": "fit_amount",
                        "table": "orders",
                        "column": "amount",
                        "sample_source": {"path": path, "column_name": "amount", "has_header": True},
                    },
                    {
                        "fit_id": "fit_category",
                        "table": "orders",
                        "column": "category",
                        "sample_source": {"path": path, "column_name": "category", "has_header": True},
                    },
                    {
                        "fit_id": "fit_ordered_on",
                        "table": "orders",
                        "column": "ordered_on",
                        "sample_source": {"path": path, "column_name": "ordered_on", "has_header": True},
                    },
                ],
            )
            validate_project(project)
            first = generate_project_rows(project)
            second = generate_project_rows(project)
            self.assertEqual(first, second)

            rows = first["orders"]
            categories = {str(row["category"]) for row in rows}
            self.assertTrue(categories.issubset({"A", "B", "C"}))
            amounts = [float(row["amount"]) for row in rows]
            self.assertGreaterEqual(min(amounts), 100.0)
            self.assertLessEqual(max(amounts), 150.0)
            ordered = [str(row["ordered_on"]) for row in rows]
            self.assertGreaterEqual(min(ordered), "2025-01-01")
            self.assertLessEqual(max(ordered), "2025-01-05")
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    def test_dg07_fixed_profile_is_used_without_sample_source(self) -> None:
        project = SchemaProject(
            name="dg07_fixed_profile",
            seed=445,
            tables=[
                TableSpec(
                    table_name="orders",
                    row_count=12,
                    columns=[
                        ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("amount", "decimal", nullable=False),
                    ],
                )
            ],
            foreign_keys=[],
            sample_profile_fits=[
                {
                    "fit_id": "fixed_amount",
                    "table": "orders",
                    "column": "amount",
                    "fixed_profile": {
                        "generator": "uniform_float",
                        "params": {"min": 77.0, "max": 77.0},
                    },
                }
            ],
        )
        validate_project(project)
        first = generate_project_rows(project)
        second = generate_project_rows(project)
        self.assertEqual(first, second)
        amounts = [float(row["amount"]) for row in first["orders"]]
        self.assertEqual(amounts, [77.0] * len(amounts))

    def test_validate_rejects_sample_source_for_unsupported_bool_dtype(self) -> None:
        bad = SchemaProject(
            name="dg07_bad_bool_infer",
            seed=446,
            tables=[
                TableSpec(
                    table_name="events",
                    row_count=5,
                    columns=[
                        ColumnSpec("event_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("flag", "bool", nullable=False),
                    ],
                )
            ],
            foreign_keys=[],
            sample_profile_fits=[
                {
                    "fit_id": "flag_fit",
                    "table": "events",
                    "column": "flag",
                    "sample_source": {"path": "tests/fixtures/city_country_pool.csv", "column_index": 0},
                }
            ],
        )
        with self.assertRaises(ValueError) as ctx:
            validate_project(bad)
        msg = str(ctx.exception)
        self.assertIn("sample_source inference does not support target dtype 'bool'", msg)
        self.assertIn("Fix:", msg)


if __name__ == "__main__":
    unittest.main()
