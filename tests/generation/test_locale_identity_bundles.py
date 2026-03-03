import unittest

from src.generator_project import generate_project_rows
from src.schema_project_model import ColumnSpec
from src.schema_project_model import ForeignKeySpec
from src.schema_project_model import SchemaProject
from src.schema_project_model import TableSpec
from src.schema_project_model import validate_project


class TestLocaleIdentityBundles(unittest.TestCase):
    def _project(self) -> SchemaProject:
        return SchemaProject(
            name="dg09_locale_bundles",
            seed=20260225,
            tables=[
                TableSpec(
                    table_name="customers",
                    row_count=40,
                    columns=[
                        ColumnSpec("customer_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("locale", "text", nullable=False),
                        ColumnSpec("country_code", "text", nullable=False),
                        ColumnSpec("currency_code", "text", nullable=False),
                        ColumnSpec("currency_symbol", "text", nullable=False),
                        ColumnSpec("first_name", "text", nullable=False),
                        ColumnSpec("last_name", "text", nullable=False),
                        ColumnSpec("full_name", "text", nullable=False),
                        ColumnSpec("address_line1", "text", nullable=False),
                        ColumnSpec("city", "text", nullable=False),
                        ColumnSpec("region", "text", nullable=False),
                        ColumnSpec("postcode", "text", nullable=False),
                        ColumnSpec("phone_e164", "text", nullable=False),
                        ColumnSpec("phone_national", "text", nullable=False),
                    ],
                ),
                TableSpec(
                    table_name="orders",
                    columns=[
                        ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("customer_id", "int", nullable=False),
                        ColumnSpec("locale", "text", nullable=False),
                        ColumnSpec("currency_code", "text", nullable=False),
                    ],
                ),
            ],
            foreign_keys=[
                ForeignKeySpec(
                    child_table="orders",
                    child_column="customer_id",
                    parent_table="customers",
                    parent_column="customer_id",
                    min_children=1,
                    max_children=2,
                )
            ],
            locale_identity_bundles=[
                {
                    "bundle_id": "customer_identity",
                    "base_table": "customers",
                    "locale_weights": {
                        "en-US": 0.4,
                        "en-GB": 0.3,
                        "fr-FR": 0.2,
                        "de-DE": 0.1,
                    },
                    "columns": {
                        "locale": "locale",
                        "country_code": "country_code",
                        "currency_code": "currency_code",
                        "currency_symbol": "currency_symbol",
                        "first_name": "first_name",
                        "last_name": "last_name",
                        "full_name": "full_name",
                        "address_line1": "address_line1",
                        "city": "city",
                        "region": "region",
                        "postcode": "postcode",
                        "phone_e164": "phone_e164",
                        "phone_national": "phone_national",
                    },
                    "related_tables": [
                        {
                            "table": "orders",
                            "via_fk": "customer_id",
                            "columns": {
                                "locale": "locale",
                                "currency_code": "currency_code",
                            },
                        }
                    ],
                }
            ],
        )

    def test_locale_identity_bundle_is_deterministic_and_fk_coherent(self) -> None:
        project = self._project()
        validate_project(project)

        rows_a = generate_project_rows(project)
        rows_b = generate_project_rows(project)
        self.assertEqual(rows_a, rows_b)

        customers = rows_a["customers"]
        orders = rows_a["orders"]
        customer_by_id = {int(row["customer_id"]): row for row in customers}
        self.assertEqual(len(customer_by_id), 40)

        expected = {
            "en-US": {"country": "US", "currency": "USD", "phone_prefix": "+1"},
            "en-GB": {"country": "GB", "currency": "GBP", "phone_prefix": "+44"},
            "fr-FR": {"country": "FR", "currency": "EUR", "phone_prefix": "+33"},
            "de-DE": {"country": "DE", "currency": "EUR", "phone_prefix": "+49"},
        }
        seen_locales: set[str] = set()

        for customer in customers:
            locale = str(customer["locale"])
            self.assertIn(locale, expected)
            seen_locales.add(locale)

            contract = expected[locale]
            self.assertEqual(str(customer["country_code"]), contract["country"])
            self.assertEqual(str(customer["currency_code"]), contract["currency"])
            self.assertTrue(str(customer["phone_e164"]).startswith(contract["phone_prefix"]))
            self.assertEqual(
                str(customer["full_name"]),
                f"{customer['first_name']} {customer['last_name']}",
            )

            postcode = str(customer["postcode"])
            if locale in {"en-US", "fr-FR", "de-DE"}:
                self.assertRegex(postcode, r"^\d{5}$")
            if locale == "en-GB":
                self.assertRegex(postcode, r"^[A-Z0-9]{2,4} [A-Z0-9]{3}$")

        self.assertGreaterEqual(len(seen_locales), 3)

        for order in orders:
            customer = customer_by_id[int(order["customer_id"])]
            self.assertEqual(order["locale"], customer["locale"])
            self.assertEqual(order["currency_code"], customer["currency_code"])

    def test_validate_rejects_unsupported_slot_and_invalid_related_fk(self) -> None:
        bad_slot = self._project()
        bad_slot.locale_identity_bundles[0]["columns"]["postal_code"] = "postcode"  # type: ignore[index]
        with self.assertRaises(ValueError) as slot_ctx:
            validate_project(bad_slot)
        self.assertIn("unsupported columns slot", str(slot_ctx.exception))

        bad_related = self._project()
        bad_related.locale_identity_bundles[0]["related_tables"][0]["via_fk"] = "order_id"  # type: ignore[index]
        with self.assertRaises(ValueError) as related_ctx:
            validate_project(bad_related)
        self.assertIn("does not directly reference base_table", str(related_ctx.exception))


if __name__ == "__main__":
    unittest.main()
