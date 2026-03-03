import unittest

from src.derived_expression import compile_derived_expression
from src.derived_expression import evaluate_derived_expression
from src.generator_project import generate_project_rows
from src.schema_project_model import ColumnSpec
from src.schema_project_model import SchemaProject
from src.schema_project_model import TableSpec
from src.schema_project_model import validate_project


class TestDerivedExpressionGenerator(unittest.TestCase):
    def test_derived_expression_is_deterministic_and_evaluates_core_dsl(self):
        project = SchemaProject(
            name="derived_expression_core",
            seed=20260224,
            tables=[
                TableSpec(
                    table_name="orders",
                    row_count=8,
                    columns=[
                        ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "base_amount",
                            "int",
                            nullable=False,
                            generator="uniform_int",
                            params={"min": 100, "max": 200},
                        ),
                        ColumnSpec(
                            "discount_text",
                            "text",
                            nullable=False,
                            generator="choice_weighted",
                            params={"choices": ["0", "5", "10"], "weights": [0.2, 0.5, 0.3]},
                        ),
                        ColumnSpec("is_vip", "bool", nullable=False),
                        ColumnSpec(
                            "label_prefix",
                            "text",
                            nullable=False,
                            generator="choice_weighted",
                            params={"choices": ["ORD", "INV"], "weights": [0.6, 0.4]},
                        ),
                        ColumnSpec(
                            "discount_amount",
                            "int",
                            nullable=False,
                            generator="derived_expr",
                            params={"expression": "to_int(discount_text)"},
                            depends_on=["discount_text"],
                        ),
                        ColumnSpec(
                            "net_amount",
                            "decimal",
                            nullable=False,
                            generator="derived_expr",
                            params={"expression": "to_decimal(base_amount) - to_decimal(discount_amount)"},
                            depends_on=["base_amount", "discount_amount"],
                        ),
                        ColumnSpec(
                            "tier",
                            "text",
                            nullable=False,
                            generator="derived_expr",
                            params={"expression": "'VIP' if to_bool(is_vip) else 'STD'"},
                            depends_on=["is_vip"],
                        ),
                        ColumnSpec(
                            "code",
                            "text",
                            nullable=False,
                            generator="derived_expr",
                            params={"expression": "concat(label_prefix, '-', to_text(base_amount))"},
                            depends_on=["label_prefix", "base_amount"],
                        ),
                        ColumnSpec(
                            "safe_div",
                            "decimal",
                            nullable=False,
                            generator="derived_expr",
                            params={
                                "expression": "to_decimal(base_amount) / (to_decimal(discount_amount) if discount_amount != 0 else 1.0)"
                            },
                            depends_on=["base_amount", "discount_amount"],
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

        for row in rows_a["orders"]:
            expected_discount = int(row["discount_text"])
            self.assertEqual(row["discount_amount"], expected_discount)

            expected_net = float(row["base_amount"]) - float(expected_discount)
            self.assertAlmostEqual(float(row["net_amount"]), expected_net)

            expected_tier = "VIP" if bool(row["is_vip"]) else "STD"
            self.assertEqual(row["tier"], expected_tier)

            self.assertEqual(row["code"], f"{row['label_prefix']}-{row['base_amount']}")

            denominator = float(expected_discount) if expected_discount != 0 else 1.0
            expected_div = float(row["base_amount"]) / denominator
            self.assertAlmostEqual(float(row["safe_div"]), expected_div)

    def test_col_function_supports_non_identifier_column_names(self):
        project = SchemaProject(
            name="derived_expression_col_helper",
            seed=9,
            tables=[
                TableSpec(
                    table_name="metrics",
                    row_count=4,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "base amount",
                            "int",
                            nullable=False,
                            generator="uniform_int",
                            params={"min": 10, "max": 20},
                        ),
                        ColumnSpec(
                            "double_amount",
                            "decimal",
                            nullable=False,
                            generator="derived_expr",
                            params={"expression": "to_decimal(col('base amount')) * 2"},
                            depends_on=["base amount"],
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )
        validate_project(project)
        rows = generate_project_rows(project)

        for row in rows["metrics"]:
            self.assertAlmostEqual(float(row["double_amount"]), float(row["base amount"]) * 2.0)

    def test_validate_rejects_invalid_expression_syntax(self):
        bad = SchemaProject(
            name="derived_expression_bad_syntax",
            seed=1,
            tables=[
                TableSpec(
                    table_name="t",
                    row_count=1,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec("base", "int", nullable=False),
                        ColumnSpec(
                            "x",
                            "int",
                            nullable=False,
                            generator="derived_expr",
                            params={"expression": "base +"},
                            depends_on=["base"],
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            validate_project(bad)
        msg = str(ctx.exception)
        self.assertIn("expression syntax is invalid", msg)
        self.assertIn("Fix:", msg)

    def test_validate_rejects_forbidden_ast_nodes(self):
        bad = SchemaProject(
            name="derived_expression_bad_ast",
            seed=2,
            tables=[
                TableSpec(
                    table_name="t",
                    row_count=1,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec("base", "text", nullable=False),
                        ColumnSpec(
                            "x",
                            "text",
                            nullable=False,
                            generator="derived_expr",
                            params={"expression": "col('base')[0]"},
                            depends_on=["base"],
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            validate_project(bad)
        msg = str(ctx.exception)
        self.assertIn("unsupported expression element 'Subscript'", msg)
        self.assertIn("Fix:", msg)

    def test_runtime_rejects_divide_by_zero(self):
        bad = SchemaProject(
            name="derived_expression_divide_zero",
            seed=3,
            tables=[
                TableSpec(
                    table_name="t",
                    row_count=1,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "denominator",
                            "int",
                            nullable=False,
                            generator="choice_weighted",
                            params={"choices": [0], "weights": [1.0]},
                        ),
                        ColumnSpec(
                            "ratio",
                            "decimal",
                            nullable=False,
                            generator="derived_expr",
                            params={"expression": "10 / denominator"},
                            depends_on=["denominator"],
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )
        validate_project(bad)

        with self.assertRaises(ValueError) as ctx:
            generate_project_rows(bad)
        msg = str(ctx.exception)
        self.assertIn("division by zero", msg)
        self.assertIn("Fix:", msg)

    def test_runtime_rejects_bad_cast(self):
        bad = SchemaProject(
            name="derived_expression_bad_cast",
            seed=4,
            tables=[
                TableSpec(
                    table_name="t",
                    row_count=1,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "raw",
                            "text",
                            nullable=False,
                            generator="choice_weighted",
                            params={"choices": ["abc"], "weights": [1.0]},
                        ),
                        ColumnSpec(
                            "as_int",
                            "int",
                            nullable=False,
                            generator="derived_expr",
                            params={"expression": "to_int(raw)"},
                            depends_on=["raw"],
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )
        validate_project(bad)

        with self.assertRaises(ValueError) as ctx:
            generate_project_rows(bad)
        msg = str(ctx.exception)
        self.assertIn("to_int(...) could not parse", msg)
        self.assertIn("Fix:", msg)

    def test_validate_requires_depends_on_for_all_references(self):
        bad = SchemaProject(
            name="derived_expression_missing_depends",
            seed=5,
            tables=[
                TableSpec(
                    table_name="t",
                    row_count=1,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec("base", "int", nullable=False),
                        ColumnSpec("extra", "int", nullable=False),
                        ColumnSpec(
                            "total",
                            "int",
                            nullable=False,
                            generator="derived_expr",
                            params={"expression": "base + extra"},
                            depends_on=["base"],
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            validate_project(bad)
        msg = str(ctx.exception)
        self.assertIn("requires depends_on to include referenced expression columns", msg)
        self.assertIn("extra", msg)
        self.assertIn("Fix:", msg)

    def test_validate_rejects_self_reference_and_unknown_reference(self):
        bad_self = SchemaProject(
            name="derived_expression_self_reference",
            seed=6,
            tables=[
                TableSpec(
                    table_name="t",
                    row_count=1,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "total",
                            "int",
                            nullable=False,
                            generator="derived_expr",
                            params={"expression": "total + 1"},
                            depends_on=["total"],
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )
        with self.assertRaises(ValueError) as self_ctx:
            validate_project(bad_self)
        self.assertIn("cannot reference the target column itself", str(self_ctx.exception))

        bad_unknown = SchemaProject(
            name="derived_expression_unknown_reference",
            seed=7,
            tables=[
                TableSpec(
                    table_name="t",
                    row_count=1,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec("base", "int", nullable=False),
                        ColumnSpec(
                            "total",
                            "int",
                            nullable=False,
                            generator="derived_expr",
                            params={"expression": "base + missing_col"},
                            depends_on=["base", "missing_col"],
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )
        with self.assertRaises(ValueError) as unknown_ctx:
            validate_project(bad_unknown)
        self.assertIn("expression reference 'missing_col' was not found", str(unknown_ctx.exception))

    def test_direct_evaluator_reports_missing_row_reference(self):
        compiled = compile_derived_expression("base + fee", location="Derived expression test")
        with self.assertRaises(ValueError) as ctx:
            evaluate_derived_expression(compiled, row={"base": 10}, location="Derived expression test")
        msg = str(ctx.exception)
        self.assertIn("expression reference 'fee' is not available", msg)
        self.assertIn("Fix:", msg)


if __name__ == "__main__":
    unittest.main()
