import unittest
from collections import Counter
from dataclasses import replace

from src.generator_project import generate_project_rows
from src.schema_project_model import ColumnSpec
from src.schema_project_model import ForeignKeySpec
from src.schema_project_model import SchemaProject
from src.schema_project_model import TableSpec
from src.schema_project_model import validate_project


class TestChildCardinalityDistribution(unittest.TestCase):
    def _single_fk_project(
        self,
        *,
        distribution: dict[str, object] | None,
        seed: int = 20260225,
        parent_selection: dict[str, object] | None = None,
    ) -> SchemaProject:
        return SchemaProject(
            name="dg08_single_fk",
            seed=seed,
            tables=[
                TableSpec(
                    table_name="customers",
                    row_count=40,
                    columns=[
                        ColumnSpec("customer_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "cohort",
                            "text",
                            nullable=False,
                            generator="derived_expr",
                            params={"expression": "'VIP' if customer_id <= 10 else 'STD'"},
                            depends_on=["customer_id"],
                        ),
                    ],
                ),
                TableSpec(
                    table_name="orders",
                    columns=[
                        ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("customer_id", "int", nullable=False),
                    ],
                ),
            ],
            foreign_keys=[
                ForeignKeySpec(
                    child_table="orders",
                    child_column="customer_id",
                    parent_table="customers",
                    parent_column="customer_id",
                    min_children=1,
                    max_children=6,
                    parent_selection=parent_selection,
                    child_count_distribution=distribution,
                )
            ],
        )

    @staticmethod
    def _counts_by_parent(rows: dict[str, list[dict[str, object]]], *, fk_column: str) -> dict[int, int]:
        counts: dict[int, int] = {}
        for row in rows["orders"]:
            parent_id = int(row[fk_column])
            counts[parent_id] = counts.get(parent_id, 0) + 1
        return counts

    def test_poisson_distribution_is_deterministic_and_respects_bounds(self) -> None:
        project = self._single_fk_project(distribution={"type": "poisson", "lambda": 1.4})
        validate_project(project)

        rows_a = generate_project_rows(project)
        rows_b = generate_project_rows(project)
        self.assertEqual(rows_a, rows_b)

        counts = self._counts_by_parent(rows_a, fk_column="customer_id")
        self.assertEqual(len(counts), 40)
        for child_count in counts.values():
            self.assertGreaterEqual(child_count, 1)
            self.assertLessEqual(child_count, 6)

        extras_hist = Counter(child_count - 1 for child_count in counts.values())
        self.assertGreater(extras_hist[0], extras_hist[4])

    def test_zipf_distribution_prefers_lower_extra_child_counts(self) -> None:
        project = self._single_fk_project(distribution={"type": "zipf", "s": 1.35}, seed=20260226)
        validate_project(project)

        rows = generate_project_rows(project)
        counts = self._counts_by_parent(rows, fk_column="customer_id")
        extras_hist = Counter(child_count - 1 for child_count in counts.values())

        self.assertGreaterEqual(extras_hist[0], extras_hist[1])
        self.assertGreater(extras_hist[0], extras_hist[3])

    def test_multi_fk_assignment_respects_bounds_with_distribution_profiles(self) -> None:
        project = SchemaProject(
            name="dg08_multi_fk",
            seed=20260227,
            tables=[
                TableSpec(
                    table_name="customer_dim",
                    row_count=25,
                    columns=[ColumnSpec("customer_id", "int", nullable=False, primary_key=True)],
                ),
                TableSpec(
                    table_name="product_dim",
                    row_count=25,
                    columns=[ColumnSpec("product_id", "int", nullable=False, primary_key=True)],
                ),
                TableSpec(
                    table_name="fact_sales",
                    row_count=90,
                    columns=[
                        ColumnSpec("sale_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("customer_id", "int", nullable=False),
                        ColumnSpec("product_id", "int", nullable=False),
                        ColumnSpec("channel", "text", nullable=False, choices=["WEB", "STORE"]),
                    ],
                ),
            ],
            foreign_keys=[
                ForeignKeySpec(
                    child_table="fact_sales",
                    child_column="customer_id",
                    parent_table="customer_dim",
                    parent_column="customer_id",
                    min_children=1,
                    max_children=6,
                    child_count_distribution={"type": "poisson", "lambda": 1.1},
                ),
                ForeignKeySpec(
                    child_table="fact_sales",
                    child_column="product_id",
                    parent_table="product_dim",
                    parent_column="product_id",
                    min_children=1,
                    max_children=6,
                    child_count_distribution={"type": "zipf", "s": 1.4},
                ),
            ],
        )
        validate_project(project)

        rows = generate_project_rows(project)
        self.assertEqual(len(rows["fact_sales"]), 90)

        customer_counts = Counter(int(row["customer_id"]) for row in rows["fact_sales"])
        product_counts = Counter(int(row["product_id"]) for row in rows["fact_sales"])
        self.assertEqual(len(customer_counts), 25)
        self.assertEqual(len(product_counts), 25)
        for count in customer_counts.values():
            self.assertGreaterEqual(count, 1)
            self.assertLessEqual(count, 6)
        for count in product_counts.values():
            self.assertGreaterEqual(count, 1)
            self.assertLessEqual(count, 6)

    def test_validate_rejects_invalid_distribution_profiles(self) -> None:
        base = self._single_fk_project(distribution={"type": "poisson", "lambda": 1.0})
        fk = base.foreign_keys[0]

        missing_lambda = replace(fk, child_count_distribution={"type": "poisson"})
        with self.assertRaises(ValueError) as missing_lambda_ctx:
            validate_project(replace(base, foreign_keys=[missing_lambda]))
        self.assertIn("child_count_distribution.lambda is required", str(missing_lambda_ctx.exception))

        invalid_zipf = replace(fk, child_count_distribution={"type": "zipf", "s": 0})
        with self.assertRaises(ValueError) as invalid_zipf_ctx:
            validate_project(replace(base, foreign_keys=[invalid_zipf]))
        self.assertIn("child_count_distribution.s must be a finite value > 0", str(invalid_zipf_ctx.exception))

        unsupported = replace(fk, child_count_distribution={"type": "gamma"})
        with self.assertRaises(ValueError) as unsupported_ctx:
            validate_project(replace(base, foreign_keys=[unsupported]))
        self.assertIn("unsupported child_count_distribution.type", str(unsupported_ctx.exception))

    def test_distribution_can_be_combined_with_parent_selection(self) -> None:
        project = self._single_fk_project(
            distribution={"type": "poisson", "lambda": 1.6},
            seed=20260228,
            parent_selection={
                "parent_attribute": "cohort",
                "weights": {"VIP": 6.0, "STD": 1.0},
                "default_weight": 1.0,
            },
        )
        validate_project(project)
        rows = generate_project_rows(project)

        cohort_by_customer = {int(row["customer_id"]): str(row["cohort"]) for row in rows["customers"]}
        counts = self._counts_by_parent(rows, fk_column="customer_id")
        vip_counts = [count for customer_id, count in counts.items() if cohort_by_customer[customer_id] == "VIP"]
        std_counts = [count for customer_id, count in counts.items() if cohort_by_customer[customer_id] == "STD"]
        self.assertTrue(vip_counts and std_counts)
        self.assertGreater(sum(vip_counts) / len(vip_counts), sum(std_counts) / len(std_counts))
        for child_count in counts.values():
            self.assertGreaterEqual(child_count, 1)
            self.assertLessEqual(child_count, 6)


if __name__ == "__main__":
    unittest.main()
