from __future__ import annotations

import unittest

from src.schema_project_model import ColumnSpec
from src.schema_project_model import ForeignKeySpec
from src.schema_project_model import SchemaProject
from src.schema_project_model import TableSpec
from src.schema_project_model import validate_project


class ValidationParityContractTests(unittest.TestCase):
    def assert_validation_error(self, project: SchemaProject, expected: str) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_project(project)
        self.assertEqual(str(ctx.exception), expected)

    def test_sample_csv_error_contract(self) -> None:
        project = SchemaProject(
            name="p",
            tables=[
                TableSpec(
                    "t",
                    [
                        ColumnSpec("id", "int", primary_key=True, nullable=False),
                        ColumnSpec("city", "text", generator="sample_csv", params={}),
                    ],
                )
            ],
        )
        self.assert_validation_error(
            project,
            "Table 't', column 'city': generator 'sample_csv' requires params.path. Fix: set params.path to a CSV file path.",
        )

    def test_correlation_error_contract(self) -> None:
        project = SchemaProject(
            name="p",
            tables=[
                TableSpec(
                    "t",
                    [
                        ColumnSpec("id", "int", primary_key=True, nullable=False),
                        ColumnSpec("a", "int"),
                        ColumnSpec("b", "int"),
                    ],
                    correlation_groups=[
                        {
                            "group_id": "g1",
                            "columns": ["a", "b"],
                            "rank_correlation": [[1.0, 0.5], [0.2, 1.0]],
                        }
                    ],
                )
            ],
        )
        self.assert_validation_error(
            project,
            "Table 't', correlation_groups[0]: rank_correlation must be symmetric but [0][1]=0.5 and [1][0]=0.2. Fix: set rank_correlation to a symmetric matrix.",
        )

    def test_scd_error_contract(self) -> None:
        project = SchemaProject(
            name="p",
            tables=[
                TableSpec(
                    "t",
                    [
                        ColumnSpec("id", "int", primary_key=True, nullable=False),
                        ColumnSpec("sku", "text", nullable=False),
                        ColumnSpec("price", "decimal"),
                    ],
                    scd_mode="scd2",
                    scd_tracked_columns=["price"],
                )
            ],
        )
        self.assert_validation_error(
            project,
            "Table 't': scd_mode='scd2' requires business_key. Fix: define business_key columns before enabling SCD.",
        )

    def test_fk_profile_error_contract(self) -> None:
        project = SchemaProject(
            name="p",
            tables=[
                TableSpec(
                    "parent",
                    [
                        ColumnSpec("id", "int", primary_key=True, nullable=False),
                        ColumnSpec("segment", "text"),
                    ],
                ),
                TableSpec(
                    "child",
                    [
                        ColumnSpec("id", "int", primary_key=True, nullable=False),
                        ColumnSpec("parent_id", "int"),
                    ],
                ),
            ],
            foreign_keys=[
                ForeignKeySpec(
                    "child",
                    "parent_id",
                    "parent",
                    "id",
                    parent_selection={"parent_attribute": "segment", "weights": {}},
                )
            ],
        )
        self.assert_validation_error(
            project,
            "Foreign key on table 'child', column 'parent_id': parent_selection.weights must be a non-empty object. Fix: set weights to a mapping of parent attribute values to non-negative numeric weights.",
        )

    def test_timeline_error_contract(self) -> None:
        project = SchemaProject(
            name="p",
            tables=[
                TableSpec(
                    "parent",
                    [
                        ColumnSpec("id", "int", primary_key=True, nullable=False),
                        ColumnSpec("created_at", "datetime"),
                    ],
                ),
                TableSpec(
                    "child",
                    [
                        ColumnSpec("id", "int", primary_key=True, nullable=False),
                        ColumnSpec("parent_id", "int"),
                        ColumnSpec("event_at", "datetime"),
                    ],
                ),
            ],
            foreign_keys=[ForeignKeySpec("child", "parent_id", "parent", "id")],
            timeline_constraints="bad",  # type: ignore[arg-type]
        )
        self.assert_validation_error(
            project,
            "Project: timeline_constraints must be a list when provided. Fix: set timeline_constraints to a list of rule objects or omit timeline_constraints.",
        )

    def test_dg06_error_contract(self) -> None:
        project = SchemaProject(
            name="p",
            tables=[TableSpec("t", [ColumnSpec("id", "int", primary_key=True, nullable=False), ColumnSpec("x", "text")])],
            data_quality_profiles=[
                {
                    "profile_id": "q1",
                    "table": "t",
                    "column": "x",
                    "kind": "bad",
                }
            ],
        )
        self.assert_validation_error(
            project,
            "Project data_quality_profiles[0]: unsupported kind 'bad'. Fix: set kind to 'missingness' or 'quality_issue'.",
        )

    def test_dg09_error_contract(self) -> None:
        project = SchemaProject(
            name="p",
            tables=[TableSpec("t", [ColumnSpec("id", "int", primary_key=True, nullable=False), ColumnSpec("name", "text")])],
            locale_identity_bundles=[
                {
                    "bundle_id": "b1",
                    "base_table": "t",
                    "entity_key": "id",
                    "columns": {"full_name": "name"},
                    "locale_weights": {"en_US": 0.0},
                }
            ],
        )
        self.assert_validation_error(
            project,
            "Project locale_identity_bundles[0]: unsupported locale_weights key 'en_US'. Fix: use one of: de-DE, en-GB, en-US, fr-FR.",
        )

    def test_dg07_error_contract(self) -> None:
        project = SchemaProject(
            name="p",
            tables=[TableSpec("t", [ColumnSpec("id", "int", primary_key=True, nullable=False), ColumnSpec("x", "text")])],
            sample_profile_fits=[
                {
                    "fit_id": "f1",
                    "table": "t",
                    "column": "x",
                }
            ],
        )
        self.assert_validation_error(
            project,
            "Project sample_profile_fits[0]: requires fixed_profile or sample_source. Fix: set fixed_profile for frozen deterministic profiles or sample_source for CSV-driven inference.",
        )

    def test_first_failure_precedence_table_before_fk(self) -> None:
        project = SchemaProject(
            name="p",
            tables=[
                TableSpec(
                    "t",
                    [
                        ColumnSpec("id", "int", primary_key=True, nullable=False),
                        ColumnSpec("city", "text", generator="sample_csv", params={}),
                    ],
                ),
                TableSpec("u", [ColumnSpec("id", "int", primary_key=True, nullable=False)]),
            ],
            foreign_keys=[ForeignKeySpec("u", "missing", "t", "id")],
        )
        self.assert_validation_error(
            project,
            "Table 't', column 'city': generator 'sample_csv' requires params.path. Fix: set params.path to a CSV file path.",
        )


if __name__ == "__main__":
    unittest.main()
