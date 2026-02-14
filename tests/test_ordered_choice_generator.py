import unittest

from src.generator_project import generate_project_rows
from src.schema_project_model import ColumnSpec, SchemaProject, TableSpec, validate_project


class TestOrderedChoiceGenerator(unittest.TestCase):
    def test_ordered_choice_progression_is_deterministic(self):
        project = SchemaProject(
            name="ordered_choice_demo",
            seed=310,
            tables=[
                TableSpec(
                    table_name="events",
                    row_count=6,
                    columns=[
                        ColumnSpec("event_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "stage",
                            "text",
                            nullable=False,
                            generator="ordered_choice",
                            params={
                                "orders": {
                                    "A": ["choice_1", "choice_2", "choice_3"],
                                    "B": ["choice_4", "choice_5", "choice_6"],
                                },
                                "order_weights": {"A": 1.0, "B": 0.0},
                                "move_weights": [0.0, 1.0],
                                "start_index": 0,
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

        stages = [row["stage"] for row in rows_a["events"]]
        self.assertEqual(stages, ["choice_1", "choice_2", "choice_3", "choice_3", "choice_3", "choice_3"])

    def test_ordered_choice_supports_int_dtype_and_weighted_stay(self):
        project = SchemaProject(
            name="ordered_choice_int",
            seed=311,
            tables=[
                TableSpec(
                    table_name="status_log",
                    row_count=4,
                    columns=[
                        ColumnSpec("status_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "status_code",
                            "int",
                            nullable=False,
                            generator="ordered_choice",
                            params={
                                "orders": {"A": [1, 2, 3], "B": [4, 5, 6]},
                                "order_weights": {"A": 0.0, "B": 1.0},
                                "move_weights": [1.0, 0.0],
                                "start_index": 0,
                            },
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )
        validate_project(project)
        rows = generate_project_rows(project)
        self.assertEqual([row["status_code"] for row in rows["status_log"]], [4, 4, 4, 4])

    def test_ordered_choice_rejects_order_weight_key_mismatch(self):
        bad = SchemaProject(
            name="ordered_choice_bad_weights",
            seed=312,
            tables=[
                TableSpec(
                    table_name="events",
                    row_count=2,
                    columns=[
                        ColumnSpec("event_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "stage",
                            "text",
                            nullable=False,
                            generator="ordered_choice",
                            params={
                                "orders": {"A": ["choice_1", "choice_2"], "B": ["choice_3", "choice_4"]},
                                "order_weights": {"A": 1.0},
                                "move_weights": [0.0, 1.0],
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
        self.assertIn("Table 'events', column 'stage'", msg)
        self.assertIn("params.order_weights keys must exactly match", msg)
        self.assertIn("Fix:", msg)


if __name__ == "__main__":
    unittest.main()
