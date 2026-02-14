import unittest
from datetime import date

from src.generator_project import generate_project_rows
from src.schema_project_model import ColumnSpec, SchemaProject, TableSpec, validate_project


class TestBusinessKeyUniqueCount(unittest.TestCase):
    def test_business_key_unique_count_allows_more_rows_than_unique_keys(self):
        project = SchemaProject(
            name="employee_history",
            seed=2026,
            tables=[
                TableSpec(
                    table_name="employees",
                    row_count=12,
                    columns=[
                        ColumnSpec("employee_sk", "int", nullable=False, primary_key=True),
                        ColumnSpec("employee_code", "text", nullable=False),
                        ColumnSpec("status", "text", nullable=False, choices=["active", "inactive"]),
                    ],
                    business_key=["employee_code"],
                    business_key_unique_count=3,
                )
            ],
            foreign_keys=[],
        )
        validate_project(project)

        rows_a = generate_project_rows(project)["employees"]
        rows_b = generate_project_rows(project)["employees"]
        self.assertEqual(rows_a, rows_b)
        self.assertEqual(len(rows_a), 12)
        self.assertEqual(len({str(r["employee_code"]) for r in rows_a}), 3)

    def test_scd2_business_key_unique_count_preserves_target_row_count(self):
        project = SchemaProject(
            name="employee_dim_scd2",
            seed=3030,
            tables=[
                TableSpec(
                    table_name="employee_dim",
                    row_count=12,
                    columns=[
                        ColumnSpec("employee_sk", "int", nullable=False, primary_key=True),
                        ColumnSpec("employee_code", "text", nullable=False),
                        ColumnSpec("department", "text", nullable=False),
                        ColumnSpec("valid_from", "date", nullable=False),
                        ColumnSpec("valid_to", "date", nullable=False),
                    ],
                    business_key=["employee_code"],
                    business_key_unique_count=4,
                    business_key_changing_columns=["department"],
                    scd_mode="scd2",
                    scd_active_from_column="valid_from",
                    scd_active_to_column="valid_to",
                )
            ],
            foreign_keys=[],
        )
        validate_project(project)

        rows = generate_project_rows(project)["employee_dim"]
        self.assertEqual(len(rows), 12)

        by_key: dict[str, list[dict[str, object]]] = {}
        for row in rows:
            key = str(row["employee_code"])
            by_key.setdefault(key, []).append(row)

        self.assertEqual(len(by_key), 4)
        self.assertTrue(
            any(len(key_rows) > 1 for key_rows in by_key.values()),
            "Expected at least one business key with multiple SCD2 versions. "
            "Fix: generate repeated business-key rows when business_key_unique_count is smaller than row_count.",
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
                    "Fix: keep active periods non-overlapping per business key.",
                )
            self.assertEqual(
                ordered[-1]["valid_to"],
                "9999-12-31",
                f"SCD2 current-row marker missing for business key '{key}'. "
                "Fix: mark final business-key version with open-ended valid_to.",
            )

    def test_validate_rejects_business_key_unique_count_above_row_count(self):
        bad_project = SchemaProject(
            name="bad_unique_count",
            seed=1,
            tables=[
                TableSpec(
                    table_name="employees",
                    row_count=5,
                    columns=[
                        ColumnSpec("employee_sk", "int", nullable=False, primary_key=True),
                        ColumnSpec("employee_code", "text", nullable=False),
                    ],
                    business_key=["employee_code"],
                    business_key_unique_count=8,
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            validate_project(bad_project)

        msg = str(ctx.exception)
        self.assertIn("business_key_unique_count", msg)
        self.assertIn("row_count", msg)
        self.assertIn("Fix:", msg)

    def test_validate_rejects_scd1_business_key_unique_count_mismatch(self):
        bad_project = SchemaProject(
            name="bad_scd1_unique_count",
            seed=2,
            tables=[
                TableSpec(
                    table_name="employee_dim",
                    row_count=6,
                    columns=[
                        ColumnSpec("employee_sk", "int", nullable=False, primary_key=True),
                        ColumnSpec("employee_code", "text", nullable=False),
                        ColumnSpec("segment", "text", nullable=False),
                    ],
                    business_key=["employee_code"],
                    business_key_unique_count=3,
                    scd_mode="scd1",
                    scd_tracked_columns=["segment"],
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            validate_project(bad_project)

        msg = str(ctx.exception)
        self.assertIn("scd_mode='scd1'", msg)
        self.assertIn("business_key_unique_count", msg)
        self.assertIn("Fix:", msg)


if __name__ == "__main__":
    unittest.main()
