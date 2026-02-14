import random
import unittest

from src.generator_project import generate_project_rows
from src.generators import GenContext, get_generator
from src.gui_schema_project import GENERATORS
from src.schema_project_model import ColumnSpec, SchemaProject, TableSpec, validate_project


class TestRealisticDistributions(unittest.TestCase):
    def test_distribution_generators_are_available_in_gui_selector(self):
        self.assertIn("uniform_int", GENERATORS)
        self.assertIn("uniform_float", GENERATORS)
        self.assertIn("normal", GENERATORS)
        self.assertIn("lognormal", GENERATORS)
        self.assertIn("choice_weighted", GENERATORS)

    def test_validate_project_rejects_normal_for_text_column(self):
        bad = SchemaProject(
            name="bad_normal_text",
            seed=7,
            tables=[
                TableSpec(
                    table_name="people",
                    row_count=2,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "score_label",
                            "text",
                            nullable=False,
                            generator="normal",
                            params={"mean": 10.0, "stdev": 1.0},
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            validate_project(bad)

        msg = str(ctx.exception)
        self.assertIn("Table 'people', column 'score_label'", msg)
        self.assertIn("generator 'normal' requires dtype int, decimal, or legacy float", msg)
        self.assertIn("Fix:", msg)

    def test_normal_supports_stddev_alias_and_is_deterministic(self):
        project = SchemaProject(
            name="normal_stddev_alias",
            seed=111,
            tables=[
                TableSpec(
                    table_name="metrics",
                    row_count=6,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "score",
                            "decimal",
                            nullable=False,
                            generator="normal",
                            params={
                                "mean": 50.0,
                                "stddev": 2.0,
                                "min": 45.0,
                                "max": 55.0,
                                "decimals": 2,
                            },
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
        for row in rows_a["metrics"]:
            self.assertGreaterEqual(row["score"], 45.0)
            self.assertLessEqual(row["score"], 55.0)

    def test_lognormal_runtime_respects_min_max_clamp(self):
        gen = get_generator("lognormal")
        ctx = GenContext(row_index=1, table="events", row={}, rng=random.Random(22))
        params = {"median": 1000.0, "sigma": 0.8, "min": 10.0, "max": 20.0, "decimals": 2}

        for _ in range(20):
            value = gen(params, ctx)
            self.assertGreaterEqual(value, 10.0)
            self.assertLessEqual(value, 20.0)

    def test_choice_weighted_rejects_all_zero_weights(self):
        bad = SchemaProject(
            name="bad_weighted_zero",
            seed=8,
            tables=[
                TableSpec(
                    table_name="labels",
                    row_count=2,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "segment",
                            "text",
                            nullable=False,
                            generator="choice_weighted",
                            params={"choices": ["A", "B"], "weights": [0, 0]},
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            validate_project(bad)

        msg = str(ctx.exception)
        self.assertIn("Table 'labels', column 'segment'", msg)
        self.assertIn("params.weights must include at least one value > 0", msg)
        self.assertIn("Fix:", msg)


if __name__ == "__main__":
    unittest.main()
