import random
import unittest

from src.generator_project import generate_project_rows
from src.generators import GenContext, get_generator
from src.schema_project_model import ColumnSpec, SchemaProject, TableSpec, validate_project


class TestSampleCsvGuardrails(unittest.TestCase):
    def test_validate_project_rejects_sample_csv_without_path(self):
        project = SchemaProject(
            name="bad_sample_csv",
            seed=1,
            tables=[
                TableSpec(
                    table_name="people",
                    row_count=2,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec("city", "text", nullable=False, generator="sample_csv", params={}),
                    ],
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            validate_project(project)

        msg = str(ctx.exception)
        self.assertIn("Table 'people', column 'city'", msg)
        self.assertIn("requires params.path", msg)
        self.assertIn("Fix:", msg)

    def test_sample_csv_generator_missing_path_is_actionable(self):
        gen = get_generator("sample_csv")
        ctx = GenContext(row_index=1, table="people", row={}, rng=random.Random(7))

        with self.assertRaises(ValueError) as err:
            gen({}, ctx)

        msg = str(err.exception)
        self.assertIn("Table 'people'", msg)
        self.assertIn("requires params.path", msg)
        self.assertIn("Fix:", msg)

    def test_repo_root_relative_sample_csv_path_is_valid(self):
        project = SchemaProject(
            name="relative_sample_csv",
            seed=2,
            tables=[
                TableSpec(
                    table_name="people",
                    row_count=3,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "city",
                            "text",
                            nullable=False,
                            generator="sample_csv",
                            params={"path": "tests/fixtures/city_country_pool.csv", "column_index": 0},
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )

        validate_project(project)
        rows = generate_project_rows(project)["people"]
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(isinstance(r["city"], str) and r["city"] for r in rows))


if __name__ == "__main__":
    unittest.main()
