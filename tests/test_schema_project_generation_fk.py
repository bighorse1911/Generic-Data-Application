import unittest

from src.schema_project_model import SchemaProject, TableSpec, ColumnSpec, ForeignKeySpec
from src.generator_project import generate_project_rows


class TestSchemaProjectGenerationFK(unittest.TestCase):
    def test_fk_integrity_in_memory(self):
        project = SchemaProject(
            name="rel-demo",
            seed=42,
            tables=[
                TableSpec(
                    table_name="customers",
                    row_count=5,
                    columns=[
                        ColumnSpec("customer_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("name", "text", nullable=False),
                    ],
                ),
                TableSpec(
                    table_name="orders",
                    columns=[
                        ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("customer_id", "int", nullable=False),
                        ColumnSpec("status", "text", nullable=False, choices=["NEW", "PAID", "SHIPPED"]),
                    ],
                ),
                TableSpec(
                    table_name="order_items",
                    columns=[
                        ColumnSpec("order_item_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("order_id", "int", nullable=False),
                        ColumnSpec("sku", "text", nullable=False),
                        ColumnSpec("qty", "int", nullable=False, min_value=1, max_value=5),
                    ],
                ),
            ],
            foreign_keys=[
                ForeignKeySpec("orders", "customer_id", "customers", "customer_id", 1, 3),
                ForeignKeySpec("order_items", "order_id", "orders", "order_id", 1, 4),
            ],
        )

        rows = generate_project_rows(project)

        customer_ids = {r["customer_id"] for r in rows["customers"]}
        order_ids = {r["order_id"] for r in rows["orders"]}

        # Orders.customer_id must exist in customers.customer_id
        for o in rows["orders"]:
            self.assertIn(o["customer_id"], customer_ids)

        # order_items.order_id must exist in orders.order_id
        for it in rows["order_items"]:
            self.assertIn(it["order_id"], order_ids)


if __name__ == "__main__":
    unittest.main()
