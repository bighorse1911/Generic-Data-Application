import unittest

from src.generator_project import generate_project_rows
from src.schema_project_model import ColumnSpec, SchemaProject, TableSpec, validate_project


class TestHierarchicalCategories(unittest.TestCase):
    def test_hierarchical_category_generation_is_deterministic_and_valid(self):
        project = SchemaProject(
            name="hierarchical_demo",
            seed=404,
            tables=[
                TableSpec(
                    table_name="products",
                    row_count=10,
                    columns=[
                        ColumnSpec("product_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("department", "text", nullable=False, choices=["Electronics", "Home"]),
                        ColumnSpec(
                            "subcategory",
                            "text",
                            nullable=False,
                            generator="hierarchical_category",
                            params={
                                "parent_column": "department",
                                "hierarchy": {
                                    "Electronics": ["Phones", "Laptops"],
                                    "Home": ["Kitchen", "Decor"],
                                },
                            },
                            depends_on=["department"],
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

        mapping = {
            "Electronics": {"Phones", "Laptops"},
            "Home": {"Kitchen", "Decor"},
        }
        for row in rows_a["products"]:
            parent = str(row["department"])
            self.assertIn(str(row["subcategory"]), mapping[parent])

    def test_hierarchical_category_requires_depends_on_parent(self):
        bad = SchemaProject(
            name="hierarchical_bad_depends",
            seed=505,
            tables=[
                TableSpec(
                    table_name="products",
                    row_count=2,
                    columns=[
                        ColumnSpec("product_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("department", "text", nullable=False, choices=["Electronics", "Home"]),
                        ColumnSpec(
                            "subcategory",
                            "text",
                            nullable=False,
                            generator="hierarchical_category",
                            params={
                                "parent_column": "department",
                                "hierarchy": {
                                    "Electronics": ["Phones"],
                                    "Home": ["Kitchen"],
                                },
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
        self.assertIn("Table 'products', column 'subcategory'", msg)
        self.assertIn("requires depends_on to include 'department'", msg)
        self.assertIn("Fix:", msg)

    def test_hierarchical_category_supports_default_children(self):
        project = SchemaProject(
            name="hierarchical_default_children",
            seed=606,
            tables=[
                TableSpec(
                    table_name="products",
                    row_count=5,
                    columns=[
                        ColumnSpec("product_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("department", "text", nullable=False, choices=["Other"]),
                        ColumnSpec(
                            "subcategory",
                            "text",
                            nullable=False,
                            generator="hierarchical_category",
                            params={
                                "parent_column": "department",
                                "hierarchy": {
                                    "Electronics": ["Phones"],
                                },
                                "default_children": ["General"],
                            },
                            depends_on=["department"],
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )
        validate_project(project)
        rows = generate_project_rows(project)["products"]
        self.assertTrue(all(row["subcategory"] == "General" for row in rows))


if __name__ == "__main__":
    unittest.main()
