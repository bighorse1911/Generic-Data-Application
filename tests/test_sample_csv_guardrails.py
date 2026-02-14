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

    def test_validate_project_rejects_dependent_sample_csv_without_depends_on(self):
        project = SchemaProject(
            name="dependent_sample_csv_missing_depends_on",
            seed=9,
            tables=[
                TableSpec(
                    table_name="people",
                    row_count=5,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "country",
                            "text",
                            nullable=False,
                            generator="sample_csv",
                            params={"path": "tests/fixtures/city_country_pool.csv", "column_index": 1},
                        ),
                        ColumnSpec(
                            "city",
                            "text",
                            nullable=False,
                            generator="sample_csv",
                            params={
                                "path": "tests/fixtures/city_country_pool.csv",
                                "column_index": 0,
                                "match_column": "country",
                                "match_column_index": 1,
                            },
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            validate_project(project)
        msg = str(ctx.exception)
        self.assertIn("Table 'people', column 'city'", msg)
        self.assertIn("requires depends_on to include 'country'", msg)
        self.assertIn("Fix:", msg)

    def test_dependent_sample_csv_generation_preserves_city_country_pairs(self):
        project = SchemaProject(
            name="dependent_sample_csv",
            seed=11,
            tables=[
                TableSpec(
                    table_name="people",
                    row_count=24,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "country",
                            "text",
                            nullable=False,
                            generator="sample_csv",
                            params={"path": "tests/fixtures/city_country_pool.csv", "column_index": 1},
                        ),
                        ColumnSpec(
                            "city",
                            "text",
                            nullable=False,
                            generator="sample_csv",
                            params={
                                "path": "tests/fixtures/city_country_pool.csv",
                                "column_index": 0,
                                "match_column": "country",
                                "match_column_index": 1,
                            },
                            depends_on=["country"],
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )

        validate_project(project)
        rows_a = generate_project_rows(project)["people"]
        rows_b = generate_project_rows(project)["people"]

        self.assertEqual(rows_a, rows_b)

        valid_pairs = {
            ("Seattle", "US"),
            ("Portland", "US"),
            ("Austin", "US"),
            ("Toronto", "CA"),
            ("Berlin", "DE"),
            ("Tokyo", "JP"),
        }
        for row in rows_a:
            self.assertIn((row["city"], row["country"]), valid_pairs)

    def test_dependent_sample_csv_runtime_error_when_no_match_rows(self):
        gen = get_generator("sample_csv")
        ctx = GenContext(row_index=1, table="people", row={"country": "XX"}, rng=random.Random(7))

        with self.assertRaises(ValueError) as err:
            gen(
                {
                    "path": "tests/fixtures/city_country_pool.csv",
                    "column_index": 0,
                    "match_column": "country",
                    "match_column_index": 1,
                },
                ctx,
            )

        msg = str(err.exception)
        self.assertIn("Table 'people', generator 'sample_csv'", msg)
        self.assertIn("no CSV rows matched", msg)
        self.assertIn("Fix:", msg)


if __name__ == "__main__":
    unittest.main()
