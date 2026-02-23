import unittest
from datetime import date

from src.generator_project import generate_project_rows
from src.schema_project_model import ColumnSpec, ForeignKeySpec, SchemaProject, TableSpec, validate_project


class TestCrossTableTemporalIntegrity(unittest.TestCase):
    @staticmethod
    def _parse_date(value: object) -> date:
        return date.fromisoformat(str(value))

    def test_chain_is_deterministic_and_within_configured_bounds(self):
        project = SchemaProject(
            name="dg03_chain_date",
            seed=901,
            tables=[
                TableSpec(
                    table_name="signup",
                    row_count=6,
                    columns=[
                        ColumnSpec("signup_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "signup_date",
                            "date",
                            nullable=False,
                            generator="date",
                            params={"start": "2025-01-01", "end": "2025-01-10"},
                        ),
                    ],
                ),
                TableSpec(
                    table_name="order_tbl",
                    columns=[
                        ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("signup_id", "int", nullable=False),
                        ColumnSpec(
                            "ordered_date",
                            "date",
                            nullable=False,
                            generator="date",
                            params={"start": "2024-12-01", "end": "2025-03-01"},
                        ),
                    ],
                ),
                TableSpec(
                    table_name="ship_tbl",
                    columns=[
                        ColumnSpec("ship_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("order_id", "int", nullable=False),
                        ColumnSpec(
                            "shipped_date",
                            "date",
                            nullable=False,
                            generator="date",
                            params={"start": "2024-12-01", "end": "2025-04-01"},
                        ),
                    ],
                ),
                TableSpec(
                    table_name="invoice_tbl",
                    columns=[
                        ColumnSpec("invoice_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("ship_id", "int", nullable=False),
                        ColumnSpec(
                            "invoiced_date",
                            "date",
                            nullable=False,
                            generator="date",
                            params={"start": "2024-12-01", "end": "2025-06-01"},
                        ),
                    ],
                ),
            ],
            foreign_keys=[
                ForeignKeySpec("order_tbl", "signup_id", "signup", "signup_id", 1, 1),
                ForeignKeySpec("ship_tbl", "order_id", "order_tbl", "order_id", 1, 1),
                ForeignKeySpec("invoice_tbl", "ship_id", "ship_tbl", "ship_id", 1, 1),
            ],
            timeline_constraints=[
                {
                    "rule_id": "signup_to_order",
                    "child_table": "order_tbl",
                    "child_column": "ordered_date",
                    "references": [
                        {
                            "parent_table": "signup",
                            "parent_column": "signup_date",
                            "via_child_fk": "signup_id",
                            "direction": "after",
                            "min_days": 0,
                            "max_days": 5,
                        }
                    ],
                },
                {
                    "rule_id": "order_to_ship",
                    "child_table": "ship_tbl",
                    "child_column": "shipped_date",
                    "references": [
                        {
                            "parent_table": "order_tbl",
                            "parent_column": "ordered_date",
                            "via_child_fk": "order_id",
                            "direction": "after",
                            "min_days": 1,
                            "max_days": 3,
                        }
                    ],
                },
                {
                    "rule_id": "ship_to_invoice",
                    "child_table": "invoice_tbl",
                    "child_column": "invoiced_date",
                    "references": [
                        {
                            "parent_table": "ship_tbl",
                            "parent_column": "shipped_date",
                            "via_child_fk": "ship_id",
                            "direction": "after",
                            "min_days": 0,
                            "max_days": 7,
                        }
                    ],
                },
            ],
        )
        validate_project(project)
        rows_a = generate_project_rows(project)
        rows_b = generate_project_rows(project)
        self.assertEqual(rows_a, rows_b)

        signup_by_id = {int(row["signup_id"]): row for row in rows_a["signup"]}
        for row in rows_a["order_tbl"]:
            parent = signup_by_id[int(row["signup_id"])]
            delta = (self._parse_date(row["ordered_date"]) - self._parse_date(parent["signup_date"])).days
            self.assertGreaterEqual(delta, 0)
            self.assertLessEqual(delta, 5)

        orders_by_id = {int(row["order_id"]): row for row in rows_a["order_tbl"]}
        for row in rows_a["ship_tbl"]:
            parent = orders_by_id[int(row["order_id"])]
            delta = (self._parse_date(row["shipped_date"]) - self._parse_date(parent["ordered_date"])).days
            self.assertGreaterEqual(delta, 1)
            self.assertLessEqual(delta, 3)

        ships_by_id = {int(row["ship_id"]): row for row in rows_a["ship_tbl"]}
        for row in rows_a["invoice_tbl"]:
            parent = ships_by_id[int(row["ship_id"])]
            delta = (self._parse_date(row["invoiced_date"]) - self._parse_date(parent["shipped_date"])).days
            self.assertGreaterEqual(delta, 0)
            self.assertLessEqual(delta, 7)

    def test_preserve_valid_value(self):
        project = SchemaProject(
            name="dg03_preserve_valid",
            seed=902,
            tables=[
                TableSpec(
                    table_name="parent_tbl",
                    row_count=3,
                    columns=[
                        ColumnSpec("parent_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "parent_date",
                            "date",
                            nullable=False,
                            generator="date",
                            params={"start": "2025-01-10", "end": "2025-01-10"},
                        ),
                    ],
                ),
                TableSpec(
                    table_name="child_tbl",
                    columns=[
                        ColumnSpec("child_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("parent_id", "int", nullable=False),
                        ColumnSpec(
                            "child_date",
                            "date",
                            nullable=False,
                            generator="date",
                            params={"start": "2025-01-12", "end": "2025-01-12"},
                        ),
                    ],
                ),
            ],
            foreign_keys=[ForeignKeySpec("child_tbl", "parent_id", "parent_tbl", "parent_id", 1, 1)],
            timeline_constraints=[
                {
                    "rule_id": "valid_keep",
                    "child_table": "child_tbl",
                    "child_column": "child_date",
                    "references": [
                        {
                            "parent_table": "parent_tbl",
                            "parent_column": "parent_date",
                            "via_child_fk": "parent_id",
                            "direction": "after",
                            "min_days": 1,
                            "max_days": 3,
                        }
                    ],
                }
            ],
        )
        rows = generate_project_rows(project)["child_tbl"]
        self.assertEqual({str(row["child_date"]) for row in rows}, {"2025-01-12"})

    def test_adjust_invalid_value_clamps_to_boundary(self):
        project = SchemaProject(
            name="dg03_adjust_invalid",
            seed=903,
            tables=[
                TableSpec(
                    table_name="parent_tbl",
                    row_count=3,
                    columns=[
                        ColumnSpec("parent_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "parent_date",
                            "date",
                            nullable=False,
                            generator="date",
                            params={"start": "2025-01-10", "end": "2025-01-10"},
                        ),
                    ],
                ),
                TableSpec(
                    table_name="child_tbl",
                    columns=[
                        ColumnSpec("child_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("parent_id", "int", nullable=False),
                        ColumnSpec(
                            "child_date",
                            "date",
                            nullable=False,
                            generator="date",
                            params={"start": "2025-01-20", "end": "2025-01-20"},
                        ),
                    ],
                ),
            ],
            foreign_keys=[ForeignKeySpec("child_tbl", "parent_id", "parent_tbl", "parent_id", 1, 1)],
            timeline_constraints=[
                {
                    "rule_id": "clamp_outside",
                    "child_table": "child_tbl",
                    "child_column": "child_date",
                    "references": [
                        {
                            "parent_table": "parent_tbl",
                            "parent_column": "parent_date",
                            "via_child_fk": "parent_id",
                            "direction": "after",
                            "min_days": 1,
                            "max_days": 3,
                        }
                    ],
                }
            ],
        )
        rows = generate_project_rows(project)["child_tbl"]
        self.assertEqual({str(row["child_date"]) for row in rows}, {"2025-01-13"})

    def test_null_or_unparseable_child_value_repairs_to_lower_bound(self):
        project = SchemaProject(
            name="dg03_repair_unparseable",
            seed=904,
            tables=[
                TableSpec(
                    table_name="parent_tbl",
                    row_count=2,
                    columns=[
                        ColumnSpec("parent_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "parent_date",
                            "date",
                            nullable=False,
                            generator="date",
                            params={"start": "2025-01-10", "end": "2025-01-10"},
                        ),
                    ],
                ),
                TableSpec(
                    table_name="child_tbl",
                    columns=[
                        ColumnSpec("child_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("parent_id", "int", nullable=False),
                        ColumnSpec(
                            "child_date",
                            "date",
                            nullable=True,
                            generator="if_then",
                            params={
                                "if_column": "child_id",
                                "operator": "==",
                                "value": 1,
                                "then_value": "not-a-date",
                                "else_value": "still-not-a-date",
                            },
                            depends_on=["child_id"],
                        ),
                    ],
                ),
            ],
            foreign_keys=[ForeignKeySpec("child_tbl", "parent_id", "parent_tbl", "parent_id", 1, 1)],
            timeline_constraints=[
                {
                    "rule_id": "repair_bad_child",
                    "child_table": "child_tbl",
                    "child_column": "child_date",
                    "references": [
                        {
                            "parent_table": "parent_tbl",
                            "parent_column": "parent_date",
                            "via_child_fk": "parent_id",
                            "direction": "after",
                            "min_days": 2,
                            "max_days": 4,
                        }
                    ],
                }
            ],
        )
        rows = generate_project_rows(project)["child_tbl"]
        self.assertEqual({str(row["child_date"]) for row in rows}, {"2025-01-12"})

    def test_datetime_seconds_bounds_are_enforced(self):
        project = SchemaProject(
            name="dg03_datetime",
            seed=905,
            tables=[
                TableSpec(
                    table_name="parent_tbl",
                    row_count=2,
                    columns=[
                        ColumnSpec("parent_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "parent_ts",
                            "datetime",
                            nullable=False,
                            generator="timestamp_utc",
                            params={
                                "start": "2025-01-10T00:00:00Z",
                                "end": "2025-01-10T00:00:00Z",
                            },
                        ),
                    ],
                ),
                TableSpec(
                    table_name="child_tbl",
                    columns=[
                        ColumnSpec("child_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("parent_id", "int", nullable=False),
                        ColumnSpec(
                            "child_ts",
                            "datetime",
                            nullable=False,
                            generator="timestamp_utc",
                            params={
                                "start": "2025-01-10T00:00:20Z",
                                "end": "2025-01-10T00:00:20Z",
                            },
                        ),
                    ],
                ),
            ],
            foreign_keys=[ForeignKeySpec("child_tbl", "parent_id", "parent_tbl", "parent_id", 1, 1)],
            timeline_constraints=[
                {
                    "rule_id": "dt_after",
                    "child_table": "child_tbl",
                    "child_column": "child_ts",
                    "references": [
                        {
                            "parent_table": "parent_tbl",
                            "parent_column": "parent_ts",
                            "via_child_fk": "parent_id",
                            "direction": "after",
                            "min_seconds": 30,
                            "max_seconds": 90,
                        }
                    ],
                }
            ],
        )
        rows = generate_project_rows(project)["child_tbl"]
        self.assertEqual({str(row["child_ts"]) for row in rows}, {"2025-01-10T00:00:30Z"})

    def test_multi_parent_interval_intersection_uses_combined_bounds(self):
        project = SchemaProject(
            name="dg03_multi_parent",
            seed=906,
            tables=[
                TableSpec(
                    table_name="parent_a",
                    row_count=1,
                    columns=[
                        ColumnSpec("a_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "a_date",
                            "date",
                            nullable=False,
                            generator="date",
                            params={"start": "2025-01-10", "end": "2025-01-10"},
                        ),
                    ],
                ),
                TableSpec(
                    table_name="parent_b",
                    row_count=1,
                    columns=[
                        ColumnSpec("b_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "b_date",
                            "date",
                            nullable=False,
                            generator="date",
                            params={"start": "2025-01-12", "end": "2025-01-12"},
                        ),
                    ],
                ),
                TableSpec(
                    table_name="child_tbl",
                    row_count=1,
                    columns=[
                        ColumnSpec("child_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("a_id", "int", nullable=False),
                        ColumnSpec("b_id", "int", nullable=False),
                        ColumnSpec(
                            "event_date",
                            "date",
                            nullable=True,
                            generator="date",
                            params={"start": "2025-02-01", "end": "2025-02-01", "null_rate": 1.0},
                        ),
                    ],
                ),
            ],
            foreign_keys=[
                ForeignKeySpec("child_tbl", "a_id", "parent_a", "a_id", 1, 1),
                ForeignKeySpec("child_tbl", "b_id", "parent_b", "b_id", 1, 1),
            ],
            timeline_constraints=[
                {
                    "rule_id": "multi_ref",
                    "child_table": "child_tbl",
                    "child_column": "event_date",
                    "references": [
                        {
                            "parent_table": "parent_a",
                            "parent_column": "a_date",
                            "via_child_fk": "a_id",
                            "direction": "after",
                            "min_days": 1,
                            "max_days": 5,
                        },
                        {
                            "parent_table": "parent_b",
                            "parent_column": "b_date",
                            "via_child_fk": "b_id",
                            "direction": "before",
                            "min_days": 0,
                            "max_days": 2,
                        },
                    ],
                }
            ],
        )
        rows = generate_project_rows(project)["child_tbl"]
        self.assertEqual(rows[0]["event_date"], "2025-01-11")

    def test_empty_intersection_raises_actionable_runtime_error(self):
        project = SchemaProject(
            name="dg03_empty_intersection",
            seed=907,
            tables=[
                TableSpec(
                    table_name="parent_a",
                    row_count=1,
                    columns=[
                        ColumnSpec("a_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "a_date",
                            "date",
                            nullable=False,
                            generator="date",
                            params={"start": "2025-01-10", "end": "2025-01-10"},
                        ),
                    ],
                ),
                TableSpec(
                    table_name="parent_b",
                    row_count=1,
                    columns=[
                        ColumnSpec("b_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "b_date",
                            "date",
                            nullable=False,
                            generator="date",
                            params={"start": "2025-01-01", "end": "2025-01-01"},
                        ),
                    ],
                ),
                TableSpec(
                    table_name="child_tbl",
                    row_count=1,
                    columns=[
                        ColumnSpec("child_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("a_id", "int", nullable=False),
                        ColumnSpec("b_id", "int", nullable=False),
                        ColumnSpec("event_date", "date", nullable=False, generator="date"),
                    ],
                ),
            ],
            foreign_keys=[
                ForeignKeySpec("child_tbl", "a_id", "parent_a", "a_id", 1, 1),
                ForeignKeySpec("child_tbl", "b_id", "parent_b", "b_id", 1, 1),
            ],
            timeline_constraints=[
                {
                    "rule_id": "empty_rule",
                    "child_table": "child_tbl",
                    "child_column": "event_date",
                    "references": [
                        {
                            "parent_table": "parent_a",
                            "parent_column": "a_date",
                            "via_child_fk": "a_id",
                            "direction": "after",
                            "min_days": 5,
                            "max_days": 6,
                        },
                        {
                            "parent_table": "parent_b",
                            "parent_column": "b_date",
                            "via_child_fk": "b_id",
                            "direction": "before",
                            "min_days": 0,
                            "max_days": 1,
                        },
                    ],
                }
            ],
        )
        with self.assertRaises(ValueError) as ctx:
            generate_project_rows(project)
        msg = str(ctx.exception)
        self.assertIn("timeline interval intersection is empty", msg)
        self.assertIn("Fix:", msg)

    def test_validator_rejects_bad_direction_and_fk_linkage(self):
        bad_direction = SchemaProject(
            name="dg03_bad_direction",
            seed=908,
            tables=[
                TableSpec(
                    table_name="parent_tbl",
                    row_count=1,
                    columns=[
                        ColumnSpec("parent_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("parent_date", "date", nullable=False, generator="date"),
                    ],
                ),
                TableSpec(
                    table_name="child_tbl",
                    columns=[
                        ColumnSpec("child_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("parent_id", "int", nullable=False),
                        ColumnSpec("child_date", "date", nullable=False, generator="date"),
                    ],
                ),
            ],
            foreign_keys=[ForeignKeySpec("child_tbl", "parent_id", "parent_tbl", "parent_id", 1, 1)],
            timeline_constraints=[
                {
                    "rule_id": "bad_dir",
                    "child_table": "child_tbl",
                    "child_column": "child_date",
                    "references": [
                        {
                            "parent_table": "parent_tbl",
                            "parent_column": "parent_date",
                            "via_child_fk": "parent_id",
                            "direction": "sideways",
                            "min_days": 0,
                            "max_days": 1,
                        }
                    ],
                }
            ],
        )
        with self.assertRaises(ValueError) as direction_ctx:
            validate_project(bad_direction)
        self.assertIn("unsupported direction", str(direction_ctx.exception))
        self.assertIn("Fix:", str(direction_ctx.exception))

        bad_link = SchemaProject(
            name="dg03_bad_link",
            seed=909,
            tables=[
                TableSpec(
                    table_name="parent_a",
                    row_count=1,
                    columns=[
                        ColumnSpec("a_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("a_date", "date", nullable=False, generator="date"),
                    ],
                ),
                TableSpec(
                    table_name="parent_b",
                    row_count=1,
                    columns=[
                        ColumnSpec("b_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("b_date", "date", nullable=False, generator="date"),
                    ],
                ),
                TableSpec(
                    table_name="child_tbl",
                    columns=[
                        ColumnSpec("child_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("a_id", "int", nullable=False),
                        ColumnSpec("b_id", "int", nullable=False),
                        ColumnSpec("event_date", "date", nullable=False, generator="date"),
                    ],
                ),
            ],
            foreign_keys=[
                ForeignKeySpec("child_tbl", "a_id", "parent_a", "a_id", 1, 1),
                ForeignKeySpec("child_tbl", "b_id", "parent_b", "b_id", 1, 1),
            ],
            timeline_constraints=[
                {
                    "rule_id": "bad_fk_link",
                    "child_table": "child_tbl",
                    "child_column": "event_date",
                    "references": [
                        {
                            "parent_table": "parent_b",
                            "parent_column": "b_date",
                            "via_child_fk": "a_id",
                            "direction": "after",
                            "min_days": 0,
                            "max_days": 1,
                        }
                    ],
                }
            ],
        )
        with self.assertRaises(ValueError) as linkage_ctx:
            validate_project(bad_link)
        self.assertIn("does not directly reference parent_table", str(linkage_ctx.exception))
        self.assertIn("Fix:", str(linkage_ctx.exception))


if __name__ == "__main__":
    unittest.main()
