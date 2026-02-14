import unittest
from datetime import date, datetime

from src.generator_project import generate_project_rows
from src.schema_project_model import ColumnSpec, SchemaProject, TableSpec, validate_project


class TestTimeAwareConstraints(unittest.TestCase):
    def test_time_offset_date_generation_is_deterministic_and_in_range(self):
        project = SchemaProject(
            name="time_offset_date",
            seed=2026,
            tables=[
                TableSpec(
                    table_name="contracts",
                    row_count=8,
                    columns=[
                        ColumnSpec("contract_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "effective_on",
                            "date",
                            nullable=False,
                            generator="date",
                            params={"start": "2024-01-01", "end": "2024-01-10"},
                        ),
                        ColumnSpec(
                            "expires_on",
                            "date",
                            nullable=False,
                            generator="time_offset",
                            params={
                                "base_column": "effective_on",
                                "direction": "after",
                                "min_days": 30,
                                "max_days": 90,
                            },
                            depends_on=["effective_on"],
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )
        validate_project(project)

        rows_a = generate_project_rows(project)
        rows_b = generate_project_rows(project)
        self.assertEqual(rows_a, rows_b)

        for row in rows_a["contracts"]:
            start_d = date.fromisoformat(str(row["effective_on"]))
            end_d = date.fromisoformat(str(row["expires_on"]))
            delta_days = (end_d - start_d).days
            self.assertGreaterEqual(delta_days, 30)
            self.assertLessEqual(delta_days, 90)

    def test_time_offset_datetime_generation_supports_before_direction(self):
        project = SchemaProject(
            name="time_offset_datetime",
            seed=2026,
            tables=[
                TableSpec(
                    table_name="events",
                    row_count=6,
                    columns=[
                        ColumnSpec("event_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "event_at",
                            "datetime",
                            nullable=False,
                            generator="timestamp_utc",
                            params={
                                "start": "2024-06-01T00:00:00Z",
                                "end": "2024-06-01T00:10:00Z",
                            },
                        ),
                        ColumnSpec(
                            "window_open_at",
                            "datetime",
                            nullable=False,
                            generator="time_offset",
                            params={
                                "base_column": "event_at",
                                "direction": "before",
                                "min_seconds": 60,
                                "max_seconds": 300,
                            },
                            depends_on=["event_at"],
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )
        validate_project(project)
        rows = generate_project_rows(project)

        for row in rows["events"]:
            event_dt = datetime.fromisoformat(str(row["event_at"]).replace("Z", "+00:00"))
            window_dt = datetime.fromisoformat(str(row["window_open_at"]).replace("Z", "+00:00"))
            delta_seconds = int((event_dt - window_dt).total_seconds())
            self.assertGreaterEqual(delta_seconds, 60)
            self.assertLessEqual(delta_seconds, 300)

    def test_time_offset_requires_depends_on_source_column(self):
        bad = SchemaProject(
            name="time_offset_bad_depends",
            seed=9,
            tables=[
                TableSpec(
                    table_name="orders",
                    row_count=2,
                    columns=[
                        ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("ordered_on", "date", nullable=False, generator="date"),
                        ColumnSpec(
                            "ship_on",
                            "date",
                            nullable=False,
                            generator="time_offset",
                            params={"base_column": "ordered_on", "min_days": 1, "max_days": 2},
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            validate_project(bad)

        msg = str(ctx.exception)
        self.assertIn("Table 'orders', column 'ship_on'", msg)
        self.assertIn("requires depends_on to include 'ordered_on'", msg)
        self.assertIn("Fix:", msg)

    def test_time_offset_rejects_mismatched_source_dtype(self):
        bad = SchemaProject(
            name="time_offset_bad_dtype",
            seed=9,
            tables=[
                TableSpec(
                    table_name="orders",
                    row_count=2,
                    columns=[
                        ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("ordered_at", "datetime", nullable=False, generator="timestamp_utc"),
                        ColumnSpec(
                            "ship_on",
                            "date",
                            nullable=False,
                            generator="time_offset",
                            params={"base_column": "ordered_at", "min_days": 1, "max_days": 2},
                            depends_on=["ordered_at"],
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            validate_project(bad)

        msg = str(ctx.exception)
        self.assertIn("Table 'orders', column 'ship_on'", msg)
        self.assertIn("source and target dtypes to match", msg)
        self.assertIn("Fix:", msg)


if __name__ == "__main__":
    unittest.main()
