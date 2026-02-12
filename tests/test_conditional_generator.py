import unittest

from src.generator_project import generate_project_rows
from src.schema_project_model import ColumnSpec, SchemaProject, TableSpec, validate_project


class TestConditionalGenerator(unittest.TestCase):
    def test_if_then_generator_is_deterministic_and_branches_from_source_column(self):
        project = SchemaProject(
            name="if_then_demo",
            seed=77,
            tables=[
                TableSpec(
                    table_name="customers",
                    row_count=8,
                    columns=[
                        ColumnSpec("customer_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("is_vip", "bool", nullable=False),
                        ColumnSpec(
                            "tier",
                            "text",
                            nullable=False,
                            generator="if_then",
                            params={
                                "if_column": "is_vip",
                                "operator": "==",
                                "value": 1,
                                "then_value": "VIP",
                                "else_value": "STANDARD",
                            },
                            depends_on=["is_vip"],
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

        for row in rows_a["customers"]:
            expected = "VIP" if row["is_vip"] == 1 else "STANDARD"
            self.assertEqual(
                row["tier"],
                expected,
                "Conditional generator branch output mismatch. "
                "Fix: ensure if_then evaluates against the source column value.",
            )

    def test_if_then_requires_depends_on_source_column(self):
        bad = SchemaProject(
            name="if_then_bad_depends",
            seed=3,
            tables=[
                TableSpec(
                    table_name="customers",
                    row_count=2,
                    columns=[
                        ColumnSpec("customer_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("is_vip", "bool", nullable=False),
                        ColumnSpec(
                            "tier",
                            "text",
                            nullable=False,
                            generator="if_then",
                            params={
                                "if_column": "is_vip",
                                "operator": "==",
                                "value": 1,
                                "then_value": "VIP",
                                "else_value": "STANDARD",
                            },
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            validate_project(bad)

        msg = str(ctx.exception)
        self.assertIn("Table 'customers', column 'tier'", msg)
        self.assertIn("requires depends_on to include 'is_vip'", msg)
        self.assertIn("Fix:", msg)

    def test_if_then_rejects_unsupported_operator(self):
        bad = SchemaProject(
            name="if_then_bad_operator",
            seed=3,
            tables=[
                TableSpec(
                    table_name="customers",
                    row_count=2,
                    columns=[
                        ColumnSpec("customer_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("is_vip", "bool", nullable=False),
                        ColumnSpec(
                            "tier",
                            "text",
                            nullable=False,
                            generator="if_then",
                            params={
                                "if_column": "is_vip",
                                "operator": ">",
                                "value": 0,
                                "then_value": "VIP",
                                "else_value": "STANDARD",
                            },
                            depends_on=["is_vip"],
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            validate_project(bad)

        msg = str(ctx.exception)
        self.assertIn("Table 'customers', column 'tier'", msg)
        self.assertIn("unsupported operator", msg)
        self.assertIn("Fix:", msg)


if __name__ == "__main__":
    unittest.main()
