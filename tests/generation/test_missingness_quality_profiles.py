import unittest

from src.generator_project import generate_project_rows
from src.schema_project_model import ColumnSpec
from src.schema_project_model import SchemaProject
from src.schema_project_model import TableSpec
from src.schema_project_model import validate_project


class TestMissingnessQualityProfiles(unittest.TestCase):
    def test_mar_missingness_is_deterministic_and_weighted_by_driver_column(self) -> None:
        project = SchemaProject(
            name="dg06_mar_missingness",
            seed=9021,
            tables=[
                TableSpec(
                    table_name="customers",
                    row_count=500,
                    columns=[
                        ColumnSpec("customer_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "segment",
                            "text",
                            nullable=False,
                            generator="choice_weighted",
                            params={"choices": ["VIP", "STD"], "weights": [1.0, 1.0]},
                        ),
                        ColumnSpec(
                            "note",
                            "text",
                            nullable=True,
                            generator="choice_weighted",
                            params={"choices": ["ok", "ok2", "ok3"], "weights": [1.0, 1.0, 1.0]},
                        ),
                    ],
                )
            ],
            foreign_keys=[],
            data_quality_profiles=[
                {
                    "profile_id": "mar_segment_note",
                    "table": "customers",
                    "column": "note",
                    "kind": "missingness",
                    "mechanism": "mar",
                    "base_rate": 0.4,
                    "driver_column": "segment",
                    "value_weights": {"VIP": 2.0, "STD": 0.2},
                    "default_weight": 0.2,
                }
            ],
        )
        validate_project(project)
        first = generate_project_rows(project)
        second = generate_project_rows(project)
        self.assertEqual(first, second)

        rows = first["customers"]
        vip_total = 0
        vip_null = 0
        std_total = 0
        std_null = 0
        for row in rows:
            segment = str(row["segment"])
            is_null = row["note"] is None
            if segment == "VIP":
                vip_total += 1
                if is_null:
                    vip_null += 1
            elif segment == "STD":
                std_total += 1
                if is_null:
                    std_null += 1

        self.assertGreater(vip_total, 0)
        self.assertGreater(std_total, 0)
        vip_rate = vip_null / vip_total
        std_rate = std_null / std_total
        self.assertGreater(vip_rate, std_rate + 0.35)

    def test_mnar_missingness_uses_target_value_weights(self) -> None:
        project = SchemaProject(
            name="dg06_mnar_missingness",
            seed=9022,
            tables=[
                TableSpec(
                    table_name="events",
                    row_count=500,
                    columns=[
                        ColumnSpec("event_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "status_raw",
                            "text",
                            nullable=False,
                            generator="choice_weighted",
                            params={"choices": ["HIGH", "LOW"], "weights": [1.0, 1.0]},
                        ),
                        ColumnSpec(
                            "status",
                            "text",
                            nullable=True,
                            generator="derived_expr",
                            params={"expression": "status_raw"},
                            depends_on=["status_raw"],
                        ),
                    ],
                )
            ],
            foreign_keys=[],
            data_quality_profiles=[
                {
                    "profile_id": "mnar_status",
                    "table": "events",
                    "column": "status",
                    "kind": "missingness",
                    "mechanism": "mnar",
                    "base_rate": 0.4,
                    "value_weights": {"HIGH": 2.0, "LOW": 0.1},
                    "default_weight": 0.1,
                }
            ],
        )
        validate_project(project)
        rows = generate_project_rows(project)["events"]

        high_total = 0
        high_null = 0
        low_total = 0
        low_null = 0
        for row in rows:
            raw = str(row["status_raw"])
            is_null = row["status"] is None
            if raw == "HIGH":
                high_total += 1
                if is_null:
                    high_null += 1
            elif raw == "LOW":
                low_total += 1
                if is_null:
                    low_null += 1

        self.assertGreater(high_total, 0)
        self.assertGreater(low_total, 0)
        high_rate = high_null / high_total
        low_rate = low_null / low_total
        self.assertGreater(high_rate, low_rate + 0.35)

    def test_quality_issue_format_error_and_drift(self) -> None:
        project = SchemaProject(
            name="dg06_quality_issues",
            seed=9023,
            tables=[
                TableSpec(
                    table_name="orders",
                    row_count=4,
                    columns=[
                        ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "order_code",
                            "text",
                            nullable=False,
                            generator="choice_weighted",
                            params={"choices": ["A", "B"], "weights": [1.0, 1.0]},
                        ),
                        ColumnSpec(
                            "amount",
                            "decimal",
                            nullable=False,
                            generator="uniform_float",
                            params={"min": 10.0, "max": 10.0},
                        ),
                    ],
                )
            ],
            foreign_keys=[],
            data_quality_profiles=[
                {
                    "profile_id": "fmt_order_code",
                    "table": "orders",
                    "column": "order_code",
                    "kind": "quality_issue",
                    "issue_type": "format_error",
                    "rate": 1.0,
                    "replacement": "BAD_CODE",
                },
                {
                    "profile_id": "drift_amount",
                    "table": "orders",
                    "column": "amount",
                    "kind": "quality_issue",
                    "issue_type": "drift",
                    "rate": 1.0,
                    "step": 0.5,
                    "start_index": 1,
                },
            ],
        )
        validate_project(project)
        rows = generate_project_rows(project)["orders"]
        self.assertEqual([row["order_code"] for row in rows], ["BAD_CODE", "BAD_CODE", "BAD_CODE", "BAD_CODE"])
        self.assertEqual([float(row["amount"]) for row in rows], [10.5, 11.0, 11.5, 12.0])

    def test_quality_issue_stale_value_uses_lagged_baseline_value(self) -> None:
        baseline = SchemaProject(
            name="dg06_stale_baseline",
            seed=9024,
            tables=[
                TableSpec(
                    table_name="readings",
                    row_count=8,
                    columns=[
                        ColumnSpec("reading_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "score",
                            "int",
                            nullable=False,
                            generator="uniform_int",
                            params={"min": 10, "max": 99},
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )
        profiled = SchemaProject(
            name="dg06_stale_profiled",
            seed=9024,
            tables=baseline.tables,
            foreign_keys=[],
            data_quality_profiles=[
                {
                    "profile_id": "stale_score",
                    "table": "readings",
                    "column": "score",
                    "kind": "quality_issue",
                    "issue_type": "stale_value",
                    "rate": 1.0,
                    "lag_rows": 1,
                }
            ],
        )
        baseline_rows = generate_project_rows(baseline)["readings"]
        profiled_rows = generate_project_rows(profiled)["readings"]

        self.assertEqual(profiled_rows[0]["score"], baseline_rows[0]["score"])
        for idx in range(1, len(profiled_rows)):
            self.assertEqual(profiled_rows[idx]["score"], baseline_rows[idx - 1]["score"])

    def test_validate_rejects_invalid_dg06_profile(self) -> None:
        bad = SchemaProject(
            name="dg06_bad_profile",
            seed=9025,
            tables=[
                TableSpec(
                    table_name="events",
                    row_count=5,
                    columns=[
                        ColumnSpec("event_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("status", "text", nullable=False),
                    ],
                )
            ],
            foreign_keys=[],
            data_quality_profiles=[
                {
                    "profile_id": "bad_drift",
                    "table": "events",
                    "column": "status",
                    "kind": "quality_issue",
                    "issue_type": "drift",
                    "rate": 0.2,
                    "step": 1,
                }
            ],
        )
        with self.assertRaises(ValueError) as ctx:
            validate_project(bad)
        self.assertIn("drift does not support dtype 'text'", str(ctx.exception))
        self.assertIn("Fix:", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
