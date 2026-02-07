import unittest
from src.generator_relational import generate_relational_data


class TestRelationalGenerator(unittest.TestCase):
    def test_repeatable(self):
        a = generate_relational_data(
            num_customers=10,
            orders_per_customer_min=1,
            orders_per_customer_max=3,
            items_per_order_min=1,
            items_per_order_max=5,
            seed=42,
        )
        b = generate_relational_data(
            num_customers=10,
            orders_per_customer_min=1,
            orders_per_customer_max=3,
            items_per_order_min=1,
            items_per_order_max=5,
            seed=42,
        )
        self.assertEqual(a, b)

    def test_fk_integrity_in_memory(self):
        data = generate_relational_data(
            num_customers=5,
            orders_per_customer_min=1,
            orders_per_customer_max=2,
            items_per_order_min=1,
            items_per_order_max=3,
            seed=1,
        )

        customer_ids = {c.customer_id for c in data.customers}
        order_ids = {o.order_id for o in data.orders}

        # Orders reference valid customers
        for o in data.orders:
            self.assertIn(o.customer_id, customer_ids)

        # Items reference valid orders
        for it in data.order_items:
            self.assertIn(it.order_id, order_ids)


if __name__ == "__main__":
    unittest.main()
