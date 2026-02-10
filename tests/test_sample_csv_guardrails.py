import random
import unittest

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


if __name__ == "__main__":
    unittest.main()
