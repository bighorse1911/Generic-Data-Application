import unittest

from src.generator_project import generate_project_rows
from src.schema_project_model import ColumnSpec, SchemaProject, TableSpec, validate_project


class TestStateTransitionGenerator(unittest.TestCase):
    def test_state_transition_is_deterministic_and_respects_transitions_and_terminal_states(self):
        project = SchemaProject(
            name="state_transition_deterministic",
            seed=410,
            tables=[
                TableSpec(
                    table_name="status_log",
                    row_count=40,
                    columns=[
                        ColumnSpec("row_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "entity_id",
                            "int",
                            nullable=False,
                            generator="choice_weighted",
                            params={"choices": [1, 2], "weights": [0.5, 0.5]},
                        ),
                        ColumnSpec(
                            "status",
                            "text",
                            nullable=False,
                            generator="state_transition",
                            params={
                                "entity_column": "entity_id",
                                "states": ["new", "active", "suspended", "closed"],
                                "start_weights": {
                                    "new": 1.0,
                                    "active": 0.0,
                                    "suspended": 0.0,
                                    "closed": 0.0,
                                },
                                "transitions": {
                                    "new": {"active": 1.0},
                                    "active": {"suspended": 0.4, "closed": 0.6},
                                    "suspended": {"active": 1.0},
                                },
                                "terminal_states": ["closed"],
                                "dwell_min": 1,
                                "dwell_max": 2,
                                "dwell_by_state": {"new": {"min": 2, "max": 2}},
                            },
                            depends_on=["entity_id"],
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

        allowed = {
            "new": {"active"},
            "active": {"suspended", "closed"},
            "suspended": {"active"},
        }
        by_entity: dict[int, list[str]] = {}
        for row in rows_a["status_log"]:
            key = int(row["entity_id"])
            by_entity.setdefault(key, []).append(str(row["status"]))

        for states in by_entity.values():
            if "closed" in states:
                first_closed = states.index("closed")
                self.assertTrue(all(state == "closed" for state in states[first_closed:]))
            for idx in range(len(states) - 1):
                previous = states[idx]
                current = states[idx + 1]
                if previous == current or previous == "closed":
                    continue
                self.assertIn(current, allowed[previous])

    def test_state_transition_dwell_by_state_is_enforced(self):
        project = SchemaProject(
            name="state_transition_dwell",
            seed=411,
            tables=[
                TableSpec(
                    table_name="timeline",
                    row_count=7,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "entity_id",
                            "int",
                            nullable=False,
                            generator="choice_weighted",
                            params={"choices": [7], "weights": [1.0]},
                        ),
                        ColumnSpec(
                            "status",
                            "text",
                            nullable=False,
                            generator="state_transition",
                            params={
                                "entity_column": "entity_id",
                                "states": ["new", "active", "closed"],
                                "start_state": "new",
                                "transitions": {
                                    "new": {"active": 1.0},
                                    "active": {"closed": 1.0},
                                },
                                "terminal_states": ["closed"],
                                "dwell_min": 1,
                                "dwell_max": 1,
                                "dwell_by_state": {"active": {"min": 2, "max": 2}},
                            },
                            depends_on=["entity_id"],
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )
        validate_project(project)
        rows = generate_project_rows(project)["timeline"]
        states = [str(row["status"]) for row in rows]
        self.assertEqual(states, ["new", "active", "active", "closed", "closed", "closed", "closed"])

    def test_validate_rejects_missing_entity_depends_on(self):
        bad = SchemaProject(
            name="state_transition_missing_depends_on",
            seed=412,
            tables=[
                TableSpec(
                    table_name="t",
                    row_count=2,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec("entity_id", "int", nullable=False),
                        ColumnSpec(
                            "status",
                            "text",
                            nullable=False,
                            generator="state_transition",
                            params={
                                "entity_column": "entity_id",
                                "states": ["new", "closed"],
                                "transitions": {"new": {"closed": 1.0}},
                                "terminal_states": ["closed"],
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
        self.assertIn("generator 'state_transition'", msg)
        self.assertIn("depends_on", msg)
        self.assertIn("Fix:", msg)

    def test_validate_rejects_invalid_dtype(self):
        bad = SchemaProject(
            name="state_transition_bad_dtype",
            seed=413,
            tables=[
                TableSpec(
                    table_name="t",
                    row_count=2,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec("entity_id", "int", nullable=False),
                        ColumnSpec(
                            "status_flag",
                            "bool",
                            nullable=False,
                            generator="state_transition",
                            params={
                                "entity_column": "entity_id",
                                "states": ["off", "on"],
                                "transitions": {"off": {"on": 1.0}},
                            },
                            depends_on=["entity_id"],
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            validate_project(bad)
        msg = str(ctx.exception)
        self.assertIn("requires dtype text or int", msg)
        self.assertIn("Fix:", msg)

    def test_validate_rejects_start_state_and_start_weights_together(self):
        bad = SchemaProject(
            name="state_transition_bad_start",
            seed=414,
            tables=[
                TableSpec(
                    table_name="t",
                    row_count=2,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec("entity_id", "int", nullable=False),
                        ColumnSpec(
                            "status",
                            "text",
                            nullable=False,
                            generator="state_transition",
                            params={
                                "entity_column": "entity_id",
                                "states": ["new", "closed"],
                                "start_state": "new",
                                "start_weights": {"new": 1.0, "closed": 0.0},
                                "transitions": {"new": {"closed": 1.0}},
                                "terminal_states": ["closed"],
                            },
                            depends_on=["entity_id"],
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            validate_project(bad)
        msg = str(ctx.exception)
        self.assertIn("start_state and params.start_weights cannot both be set", msg)
        self.assertIn("Fix:", msg)

    def test_validate_rejects_self_transition_edges(self):
        bad = SchemaProject(
            name="state_transition_self_edge",
            seed=415,
            tables=[
                TableSpec(
                    table_name="t",
                    row_count=2,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec("entity_id", "int", nullable=False),
                        ColumnSpec(
                            "status",
                            "text",
                            nullable=False,
                            generator="state_transition",
                            params={
                                "entity_column": "entity_id",
                                "states": ["new", "closed"],
                                "transitions": {"new": {"new": 1.0}},
                            },
                            depends_on=["entity_id"],
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            validate_project(bad)
        msg = str(ctx.exception)
        self.assertIn("self-transition", msg)
        self.assertIn("Fix:", msg)

    def test_validate_rejects_missing_non_terminal_transitions(self):
        bad = SchemaProject(
            name="state_transition_missing_non_terminal",
            seed=416,
            tables=[
                TableSpec(
                    table_name="t",
                    row_count=2,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec("entity_id", "int", nullable=False),
                        ColumnSpec(
                            "status",
                            "text",
                            nullable=False,
                            generator="state_transition",
                            params={
                                "entity_column": "entity_id",
                                "states": ["new", "active", "closed"],
                                "transitions": {"new": {"active": 1.0}},
                                "terminal_states": ["closed"],
                            },
                            depends_on=["entity_id"],
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            validate_project(bad)
        msg = str(ctx.exception)
        self.assertIn("missing transition weights", msg)
        self.assertIn("Fix:", msg)

    def test_state_transition_int_states_accept_stringified_transition_keys(self):
        project = SchemaProject(
            name="state_transition_int_keys",
            seed=417,
            tables=[
                TableSpec(
                    table_name="t",
                    row_count=5,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "entity_id",
                            "int",
                            nullable=False,
                            generator="choice_weighted",
                            params={"choices": [9], "weights": [1.0]},
                        ),
                        ColumnSpec(
                            "status_code",
                            "int",
                            nullable=False,
                            generator="state_transition",
                            params={
                                "entity_column": "entity_id",
                                "states": [10, 20, 30],
                                "start_weights": {"10": 1.0, "20": 0.0, "30": 0.0},
                                "transitions": {"10": {"20": 1.0}, "20": {"30": 1.0}},
                                "terminal_states": [30],
                                "dwell_min": 1,
                                "dwell_max": 1,
                            },
                            depends_on=["entity_id"],
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )
        validate_project(project)
        rows = generate_project_rows(project)["t"]
        codes = [int(row["status_code"]) for row in rows]
        self.assertEqual(codes, [10, 20, 30, 30, 30])


if __name__ == "__main__":
    unittest.main()
