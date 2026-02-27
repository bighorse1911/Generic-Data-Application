import csv
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.generator_project import generate_project_rows
from src.generator_project import generate_project_rows_streaming
from src.performance_scaling import build_performance_profile
from src.performance_scaling import run_generation_with_strategy
from src.schema_project_model import ColumnSpec, ForeignKeySpec, SchemaProject, TableSpec


class TestStreamingGeneration(unittest.TestCase):
    def _project(self) -> SchemaProject:
        return SchemaProject(
            name="streaming_demo",
            seed=101,
            tables=[
                TableSpec(
                    table_name="customers",
                    row_count=150,
                    columns=[
                        ColumnSpec("customer_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "signup_date",
                            "date",
                            nullable=False,
                            generator="date",
                            params={"start": "2025-01-01", "end": "2025-01-31"},
                        ),
                    ],
                ),
                TableSpec(
                    table_name="orders",
                    row_count=450,
                    columns=[
                        ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("customer_id", "int", nullable=False),
                        ColumnSpec(
                            "ordered_date",
                            "date",
                            nullable=False,
                            generator="date",
                            params={"start": "2024-12-20", "end": "2025-03-01"},
                        ),
                    ],
                ),
                TableSpec(
                    table_name="payments",
                    row_count=450,
                    columns=[
                        ColumnSpec("payment_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("order_id", "int", nullable=False),
                        ColumnSpec(
                            "paid_date",
                            "date",
                            nullable=False,
                            generator="date",
                            params={"start": "2024-12-20", "end": "2025-03-10"},
                        ),
                    ],
                ),
            ],
            foreign_keys=[
                ForeignKeySpec(
                    child_table="orders",
                    child_column="customer_id",
                    parent_table="customers",
                    parent_column="customer_id",
                    min_children=2,
                    max_children=4,
                    child_count_distribution={"type": "zipf", "s": 1.25},
                ),
                ForeignKeySpec(
                    child_table="payments",
                    child_column="order_id",
                    parent_table="orders",
                    parent_column="order_id",
                    min_children=1,
                    max_children=1,
                ),
            ],
            timeline_constraints=[
                {
                    "rule_id": "signup_to_order",
                    "child_table": "orders",
                    "child_column": "ordered_date",
                    "references": [
                        {
                            "parent_table": "customers",
                            "parent_column": "signup_date",
                            "via_child_fk": "customer_id",
                            "direction": "after",
                            "min_days": 0,
                            "max_days": 7,
                        }
                    ],
                },
                {
                    "rule_id": "order_to_payment",
                    "child_table": "payments",
                    "child_column": "paid_date",
                    "references": [
                        {
                            "parent_table": "orders",
                            "parent_column": "ordered_date",
                            "via_child_fk": "order_id",
                            "direction": "after",
                            "min_days": 0,
                            "max_days": 3,
                        }
                    ],
                },
            ],
        )

    def _profile_kwargs(self, *, output_mode: str) -> dict[str, object]:
        return {
            "target_tables_value": "payments",
            "row_overrides_json_value": "{\"customers\": 160}",
            "preview_row_target_value": "20",
            "output_mode_value": output_mode,
            "chunk_size_rows_value": "64",
            "preview_page_size_value": "500",
            "sqlite_batch_size_value": "128",
            "csv_buffer_rows_value": "64",
            "fk_cache_mode_value": "auto",
            "strict_deterministic_chunking_value": True,
        }

    def test_streaming_generator_matches_materialized_generation(self) -> None:
        project = self._project()
        expected = generate_project_rows(project)

        observed_order: list[str] = []
        observed_rows: dict[str, list[dict[str, object]]] = {}

        def capture(table_name: str, rows: list[dict[str, object]]) -> None:
            observed_order.append(table_name)
            observed_rows[table_name] = [dict(row) for row in rows]

        generate_project_rows_streaming(project, on_table_rows=capture)

        self.assertEqual(observed_order, ["customers", "orders", "payments"])
        self.assertEqual(observed_rows, expected)

    def test_csv_streaming_is_deterministic_and_fk_safe(self) -> None:
        project = self._project()
        profile = build_performance_profile(**self._profile_kwargs(output_mode="csv"))

        with TemporaryDirectory() as out_a, TemporaryDirectory() as out_b:
            first = run_generation_with_strategy(project, profile, output_csv_folder=out_a)
            second = run_generation_with_strategy(project, profile, output_csv_folder=out_b)

            self.assertEqual(first.selected_tables, ("customers", "orders", "payments"))
            self.assertEqual(first.selected_tables, second.selected_tables)

            for table_name in first.selected_tables:
                first_path = Path(first.csv_paths[table_name])
                second_path = Path(second.csv_paths[table_name])
                self.assertEqual(first_path.read_text(encoding="utf-8"), second_path.read_text(encoding="utf-8"))
                self.assertLessEqual(len(first.rows_by_table.get(table_name, [])), profile.preview_row_target)

            with Path(first.csv_paths["customers"]).open("r", encoding="utf-8", newline="") as handle:
                customer_ids = {int(row["customer_id"]) for row in csv.DictReader(handle)}

            with Path(first.csv_paths["orders"]).open("r", encoding="utf-8", newline="") as handle:
                order_rows = list(csv.DictReader(handle))
            for row in order_rows:
                self.assertIn(int(row["customer_id"]), customer_ids)

            order_ids = {int(row["order_id"]) for row in order_rows}
            with Path(first.csv_paths["payments"]).open("r", encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    self.assertIn(int(row["order_id"]), order_ids)

    def test_sqlite_streaming_preserves_fk_integrity(self) -> None:
        project = self._project()
        profile = build_performance_profile(**self._profile_kwargs(output_mode="sqlite"))

        with TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "streaming_demo.db"
            result = run_generation_with_strategy(project, profile, output_sqlite_path=str(db_path))

            self.assertTrue(db_path.exists())
            self.assertEqual(result.selected_tables, ("customers", "orders", "payments"))

            conn = sqlite3.connect(str(db_path))
            try:
                fk_errors = conn.execute("PRAGMA foreign_key_check;").fetchall()
                self.assertEqual(fk_errors, [])

                for table_name in result.selected_tables:
                    row_count = int(conn.execute(f"SELECT COUNT(*) FROM {table_name};").fetchone()[0])
                    self.assertEqual(row_count, result.sqlite_counts[table_name])
                    self.assertLessEqual(len(result.rows_by_table.get(table_name, [])), profile.preview_row_target)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
