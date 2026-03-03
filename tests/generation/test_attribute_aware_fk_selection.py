import unittest
from dataclasses import replace

from src.generator_project import generate_project_rows
from src.schema_project_model import ColumnSpec
from src.schema_project_model import ForeignKeySpec
from src.schema_project_model import SchemaProject
from src.schema_project_model import TableSpec
from src.schema_project_model import validate_project


class TestAttributeAwareFKSelection(unittest.TestCase):
    def _weighted_project(self, *, include_parent_selection: bool) -> SchemaProject:
        fk = ForeignKeySpec(
            child_table="orders",
            child_column="customer_id",
            parent_table="customers",
            parent_column="customer_id",
            min_children=1,
            max_children=6,
            parent_selection=(
                {
                    "parent_attribute": "cohort",
                    "weights": {"VIP": 8.0, "STD": 1.0},
                    "default_weight": 1.0,
                }
                if include_parent_selection
                else None
            ),
        )
        return SchemaProject(
            name="dg05_fk_weighted_selection",
            seed=20260224,
            tables=[
                TableSpec(
                    table_name="customers",
                    row_count=12,
                    columns=[
                        ColumnSpec("customer_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "cohort",
                            "text",
                            nullable=False,
                            generator="derived_expr",
                            params={"expression": "'VIP' if customer_id <= 3 else 'STD'"},
                            depends_on=["customer_id"],
                        ),
                    ],
                ),
                TableSpec(
                    table_name="orders",
                    columns=[
                        ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("customer_id", "int", nullable=False),
                        ColumnSpec("amount", "int", nullable=False, generator="uniform_int", params={"min": 10, "max": 50}),
                    ],
                ),
            ],
            foreign_keys=[fk],
        )

    def test_fk_parent_selection_is_deterministic_and_skews_distribution(self):
        weighted = self._weighted_project(include_parent_selection=True)
        baseline = self._weighted_project(include_parent_selection=False)
        validate_project(weighted)
        validate_project(baseline)

        weighted_rows_a = generate_project_rows(weighted)
        weighted_rows_b = generate_project_rows(weighted)
        self.assertEqual(weighted_rows_a, weighted_rows_b)

        baseline_rows = generate_project_rows(baseline)

        customer_cohort = {int(row["customer_id"]): str(row["cohort"]) for row in weighted_rows_a["customers"]}

        def _counts_by_parent(rows: dict[str, list[dict[str, object]]]) -> dict[int, int]:
            counts: dict[int, int] = {customer_id: 0 for customer_id in customer_cohort}
            for row in rows["orders"]:
                counts[int(row["customer_id"])] += 1
            return counts

        weighted_counts = _counts_by_parent(weighted_rows_a)
        baseline_counts = _counts_by_parent(baseline_rows)

        vip_weighted = [count for customer_id, count in weighted_counts.items() if customer_cohort[customer_id] == "VIP"]
        std_weighted = [count for customer_id, count in weighted_counts.items() if customer_cohort[customer_id] == "STD"]
        vip_baseline = [count for customer_id, count in baseline_counts.items() if customer_cohort[customer_id] == "VIP"]

        self.assertTrue(vip_weighted and std_weighted and vip_baseline)
        self.assertGreater(sum(vip_weighted) / len(vip_weighted), sum(std_weighted) / len(std_weighted))
        self.assertGreater(sum(vip_weighted) / len(vip_weighted), sum(vip_baseline) / len(vip_baseline))

        for count in weighted_counts.values():
            self.assertGreaterEqual(count, 1)
            self.assertLessEqual(count, 6)

    def test_validate_rejects_unknown_parent_selection_attribute(self):
        bad = self._weighted_project(include_parent_selection=True)
        bad_fk = replace(
            bad.foreign_keys[0],
            parent_selection={
                "parent_attribute": "segment",
                "weights": {"VIP": 3.0},
                "default_weight": 1.0,
            },
        )
        bad = replace(bad, foreign_keys=[bad_fk])

        with self.assertRaises(ValueError) as ctx:
            validate_project(bad)
        msg = str(ctx.exception)
        self.assertIn("parent_selection.parent_attribute 'segment' was not found", msg)
        self.assertIn("Fix:", msg)

    def test_validate_rejects_invalid_parent_selection_weights(self):
        base = self._weighted_project(include_parent_selection=True)

        bad_negative = replace(
            base.foreign_keys[0],
            parent_selection={
                "parent_attribute": "cohort",
                "weights": {"VIP": -1.0, "STD": 1.0},
                "default_weight": 1.0,
            },
        )
        with self.assertRaises(ValueError) as negative_ctx:
            validate_project(replace(base, foreign_keys=[bad_negative]))
        self.assertIn("must be a finite value >= 0", str(negative_ctx.exception))

        bad_zero = replace(
            base.foreign_keys[0],
            parent_selection={
                "parent_attribute": "cohort",
                "weights": {"VIP": 0.0, "STD": 0.0},
                "default_weight": 0.0,
            },
        )
        with self.assertRaises(ValueError) as zero_ctx:
            validate_project(replace(base, foreign_keys=[bad_zero]))
        self.assertIn("provides no positive selection weight", str(zero_ctx.exception))


if __name__ == "__main__":
    unittest.main()
