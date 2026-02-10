import os
import tempfile
import unittest
from datetime import date

from src.generator_project import generate_project_rows
from src.schema_project_io import load_project_from_json, save_project_to_json
from src.schema_project_model import ColumnSpec, SchemaProject, TableSpec, validate_project


class TestSCDGeneration(unittest.TestCase):
    def test_scd1_business_key_is_unique_and_deterministic(self):
        project = SchemaProject(
            name="scd1_demo",
            seed=321,
            tables=[
                TableSpec(
                    table_name="customer_dim",
                    row_count=6,
                    columns=[
                        ColumnSpec("customer_sk", "int", nullable=False, primary_key=True),
                        ColumnSpec("customer_code", "text", nullable=False),
                        ColumnSpec("segment", "text", nullable=False, choices=["A", "B", "C"]),
                    ],
                    business_key=["customer_code"],
                    scd_mode="scd1",
                    scd_tracked_columns=["segment"],
                )
            ],
            foreign_keys=[],
        )
        validate_project(project)

        rows_a = generate_project_rows(project)
        rows_b = generate_project_rows(project)
        self.assertEqual(rows_a, rows_b)

        rows = rows_a["customer_dim"]
        self.assertEqual(len(rows), 6)

        business_keys = [r["customer_code"] for r in rows]
        self.assertEqual(
            len(business_keys),
            len(set(business_keys)),
            "SCD1 invariant failed: expected one row per business key. "
            "Fix: enforce unique business keys for scd_mode='scd1'.",
        )

    def test_scd2_generates_history_with_non_overlapping_periods(self):
        project = SchemaProject(
            name="scd2_demo",
            seed=654,
            tables=[
                TableSpec(
                    table_name="customer_dim",
                    row_count=4,
                    columns=[
                        ColumnSpec("customer_sk", "int", nullable=False, primary_key=True),
                        ColumnSpec("customer_code", "text", nullable=False),
                        ColumnSpec("city", "text", nullable=False),
                        ColumnSpec("valid_from", "date", nullable=False),
                        ColumnSpec("valid_to", "date", nullable=False),
                    ],
                    business_key=["customer_code"],
                    scd_mode="scd2",
                    scd_tracked_columns=["city"],
                    scd_active_from_column="valid_from",
                    scd_active_to_column="valid_to",
                )
            ],
            foreign_keys=[],
        )
        validate_project(project)

        rows = generate_project_rows(project)["customer_dim"]
        self.assertGreater(
            len(rows),
            4,
            "SCD2 generation should produce multiple versions for at least some business keys. "
            "Fix: emit historical versions when scd_mode='scd2'.",
        )

        by_key: dict[str, list[dict[str, object]]] = {}
        for row in rows:
            key = str(row["customer_code"])
            by_key.setdefault(key, []).append(row)

        self.assertTrue(
            any(len(v) > 1 for v in by_key.values()),
            "SCD2 generation produced no multi-version business keys. "
            "Fix: generate at least one historical version per configured SCD2 table.",
        )

        for key, key_rows in by_key.items():
            ordered = sorted(key_rows, key=lambda r: str(r["valid_from"]))
            for i in range(len(ordered) - 1):
                prev_to = date.fromisoformat(str(ordered[i]["valid_to"]))
                next_from = date.fromisoformat(str(ordered[i + 1]["valid_from"]))
                self.assertLess(
                    prev_to,
                    next_from,
                    f"SCD2 overlap for business key '{key}'. "
                    "Fix: ensure non-overlapping active periods per business key.",
                )
            self.assertEqual(
                ordered[-1]["valid_to"],
                "9999-12-31",
                f"SCD2 current-row marker missing for business key '{key}'. "
                "Fix: mark current row with open-ended active period end.",
            )

    def test_scd_json_roundtrip_preserves_table_config(self):
        project = SchemaProject(
            name="scd_roundtrip",
            seed=123,
            tables=[
                TableSpec(
                    table_name="customer_dim",
                    row_count=3,
                    columns=[
                        ColumnSpec("customer_sk", "int", nullable=False, primary_key=True),
                        ColumnSpec("customer_code", "text", nullable=False),
                        ColumnSpec("city", "text", nullable=False),
                        ColumnSpec("valid_from", "datetime", nullable=False),
                        ColumnSpec("valid_to", "datetime", nullable=False),
                    ],
                    business_key=["customer_code"],
                    scd_mode="scd2",
                    scd_tracked_columns=["city"],
                    scd_active_from_column="valid_from",
                    scd_active_to_column="valid_to",
                )
            ],
            foreign_keys=[],
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

    def test_scd2_validation_error_is_actionable_when_period_columns_missing(self):
        bad = SchemaProject(
            name="bad_scd2",
            seed=1,
            tables=[
                TableSpec(
                    table_name="customer_dim",
                    row_count=2,
                    columns=[
                        ColumnSpec("customer_sk", "int", nullable=False, primary_key=True),
                        ColumnSpec("customer_code", "text", nullable=False),
                        ColumnSpec("city", "text", nullable=False),
                    ],
                    business_key=["customer_code"],
                    scd_mode="scd2",
                    scd_tracked_columns=["city"],
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            validate_project(bad)

        msg = str(ctx.exception)
        self.assertIn("Table 'customer_dim'", msg)
        self.assertIn("scd_mode='scd2' requires scd_active_from_column and scd_active_to_column", msg)
        self.assertIn("Fix:", msg)


if __name__ == "__main__":
    unittest.main()
