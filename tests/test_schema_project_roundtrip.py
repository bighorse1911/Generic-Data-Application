import unittest
import tempfile
import os
import json
from pathlib import Path

from src.schema_project_model import (
    SchemaProject, TableSpec, ColumnSpec, ForeignKeySpec
)
from src.schema_project_io import save_project_to_json, load_project_from_json, build_project_sql_ddl


class TestSchemaProjectRoundtrip(unittest.TestCase):
    def _project(self) -> SchemaProject:
        return SchemaProject(
            name="demo",
            seed=7,
            tables=[
                TableSpec(
                    table_name="customers",
                    row_count=3,
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
                        ColumnSpec("status", "text", nullable=False, choices=["NEW", "PAID"]),
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
        )

    def test_roundtrip_json(self):
        project = self._project()

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        path = tmp.name
        tmp.close()

        try:
            save_project_to_json(project, path)
            loaded = load_project_from_json(path)
            self.assertEqual(project, loaded)
        finally:
            try:
                os.remove(path)
            except PermissionError:
                pass

    def test_save_json_appends_sql_ddl_string(self):
        project = self._project()

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        path = tmp.name
        tmp.close()

        try:
            save_project_to_json(project, path)
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)

            self.assertIn("sql_ddl", raw)
            self.assertIsInstance(raw["sql_ddl"], str)
            self.assertEqual(raw["sql_ddl"], build_project_sql_ddl(project))
            self.assertIn('CREATE TABLE "customers"', raw["sql_ddl"])
            self.assertIn('CREATE TABLE "orders"', raw["sql_ddl"])
            self.assertIn(
                'FOREIGN KEY ("customer_id") REFERENCES "customers" ("customer_id")',
                raw["sql_ddl"],
            )
        finally:
            try:
                os.remove(path)
            except PermissionError:
                pass

    def test_load_rejects_non_string_sql_ddl_with_fix_hint(self):
        payload = {
            "name": "demo",
            "seed": 7,
            "tables": [
                {
                    "table_name": "customers",
                    "columns": [
                        {"name": "customer_id", "dtype": "int", "nullable": False, "primary_key": True},
                    ],
                }
            ],
            "foreign_keys": [],
            "sql_ddl": {"bad": "type"},
        }

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        path = tmp.name
        tmp.close()

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f)

            with self.assertRaises(ValueError) as ctx:
                load_project_from_json(path)

            msg = str(ctx.exception)
            self.assertIn("sql_ddl", msg)
            self.assertIn("must be a string", msg)
            self.assertIn("Fix:", msg)
        finally:
            try:
                os.remove(path)
            except PermissionError:
                pass

    def test_save_normalizes_sample_csv_path_to_repo_relative(self):
        fixture_csv = Path(__file__).resolve().parent / "fixtures" / "city_country_pool.csv"
        project = SchemaProject(
            name="csv_path_normalize",
            seed=12,
            tables=[
                TableSpec(
                    table_name="people",
                    row_count=2,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "city",
                            "text",
                            nullable=False,
                            generator="sample_csv",
                            params={"path": str(fixture_csv), "column_index": 0},
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        path = tmp.name
        tmp.close()

        try:
            save_project_to_json(project, path)
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)

            saved_path = raw["tables"][0]["columns"][1]["params"]["path"]
            self.assertEqual(saved_path, "tests/fixtures/city_country_pool.csv")
        finally:
            try:
                os.remove(path)
            except PermissionError:
                pass

    def test_roundtrip_preserves_correlation_groups(self):
        project = SchemaProject(
            name="corr_roundtrip",
            seed=33,
            tables=[
                TableSpec(
                    table_name="signals",
                    row_count=5,
                    columns=[
                        ColumnSpec("signal_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("a", "decimal", nullable=False),
                        ColumnSpec("b", "decimal", nullable=False),
                    ],
                    correlation_groups=[
                        {
                            "group_id": "g1",
                            "columns": ["a", "b"],
                            "rank_correlation": [[1.0, 0.8], [0.8, 1.0]],
                            "strength": 0.9,
                        }
                    ],
                )
            ],
            foreign_keys=[],
        )

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        path = tmp.name
        tmp.close()
        try:
            save_project_to_json(project, path)
            loaded = load_project_from_json(path)
            self.assertEqual(project, loaded)
        finally:
            try:
                os.remove(path)
            except PermissionError:
                pass

    def test_roundtrip_preserves_timeline_constraints(self):
        project = SchemaProject(
            name="timeline_roundtrip",
            seed=44,
            tables=[
                TableSpec(
                    table_name="signup",
                    row_count=2,
                    columns=[
                        ColumnSpec("signup_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("signup_date", "date", nullable=False, generator="date"),
                    ],
                ),
                TableSpec(
                    table_name="orders",
                    columns=[
                        ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("signup_id", "int", nullable=False),
                        ColumnSpec("ordered_date", "date", nullable=False, generator="date"),
                    ],
                ),
            ],
            foreign_keys=[
                ForeignKeySpec(
                    child_table="orders",
                    child_column="signup_id",
                    parent_table="signup",
                    parent_column="signup_id",
                    min_children=1,
                    max_children=1,
                )
            ],
            timeline_constraints=[
                {
                    "rule_id": "signup_to_order",
                    "child_table": "orders",
                    "child_column": "ordered_date",
                    "references": [
                        {
                            "parent_table": "signup",
                            "parent_column": "signup_date",
                            "via_child_fk": "signup_id",
                            "direction": "after",
                            "min_days": 0,
                            "max_days": 5,
                        }
                    ],
                }
            ],
        )

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        path = tmp.name
        tmp.close()
        try:
            save_project_to_json(project, path)
            loaded = load_project_from_json(path)
            self.assertEqual(project, loaded)
        finally:
            try:
                os.remove(path)
            except PermissionError:
                pass

    def test_roundtrip_preserves_fk_parent_selection_profile(self):
        project = SchemaProject(
            name="fk_parent_selection_roundtrip",
            seed=55,
            tables=[
                TableSpec(
                    table_name="customers",
                    row_count=3,
                    columns=[
                        ColumnSpec("customer_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("segment", "text", nullable=False, choices=["VIP", "STD"]),
                    ],
                ),
                TableSpec(
                    table_name="orders",
                    columns=[
                        ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("customer_id", "int", nullable=False),
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
                    max_children=4,
                    parent_selection={
                        "parent_attribute": "segment",
                        "weights": {"VIP": 4.0, "STD": 1.0},
                        "default_weight": 1.0,
                    },
                )
            ],
        )

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        path = tmp.name
        tmp.close()
        try:
            save_project_to_json(project, path)
            loaded = load_project_from_json(path)
            self.assertEqual(project, loaded)
        finally:
            try:
                os.remove(path)
            except PermissionError:
                pass

    def test_roundtrip_preserves_fk_child_count_distribution_profile(self):
        project = SchemaProject(
            name="fk_child_count_distribution_roundtrip",
            seed=59,
            tables=[
                TableSpec(
                    table_name="customers",
                    row_count=4,
                    columns=[ColumnSpec("customer_id", "int", nullable=False, primary_key=True)],
                ),
                TableSpec(
                    table_name="orders",
                    columns=[
                        ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("customer_id", "int", nullable=False),
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
                    max_children=5,
                    child_count_distribution={"type": "poisson", "lambda": 1.4},
                )
            ],
        )

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        path = tmp.name
        tmp.close()
        try:
            save_project_to_json(project, path)
            loaded = load_project_from_json(path)
            self.assertEqual(project, loaded)
        finally:
            try:
                os.remove(path)
            except PermissionError:
                pass

    def test_roundtrip_preserves_data_quality_profiles(self):
        project = SchemaProject(
            name="dg06_roundtrip",
            seed=56,
            tables=[
                TableSpec(
                    table_name="events",
                    row_count=3,
                    columns=[
                        ColumnSpec("event_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("segment", "text", nullable=False, choices=["A", "B"]),
                        ColumnSpec("note", "text", nullable=True),
                    ],
                )
            ],
            foreign_keys=[],
            data_quality_profiles=[
                {
                    "profile_id": "mar_note",
                    "table": "events",
                    "column": "note",
                    "kind": "missingness",
                    "mechanism": "mar",
                    "base_rate": 0.3,
                    "driver_column": "segment",
                    "value_weights": {"A": 2.0, "B": 0.2},
                    "default_weight": 0.2,
                },
                {
                    "profile_id": "fmt_note",
                    "table": "events",
                    "column": "note",
                    "kind": "quality_issue",
                    "issue_type": "format_error",
                    "rate": 0.05,
                    "replacement": "BAD_NOTE",
                },
            ],
        )

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        path = tmp.name
        tmp.close()
        try:
            save_project_to_json(project, path)
            loaded = load_project_from_json(path)
            self.assertEqual(project, loaded)
        finally:
            try:
                os.remove(path)
            except PermissionError:
                pass

    def test_roundtrip_preserves_sample_profile_fits(self):
        project = SchemaProject(
            name="dg07_roundtrip",
            seed=57,
            tables=[
                TableSpec(
                    table_name="orders",
                    row_count=3,
                    columns=[
                        ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("city", "text", nullable=False),
                    ],
                )
            ],
            foreign_keys=[],
            sample_profile_fits=[
                {
                    "fit_id": "orders_city_fit",
                    "table": "orders",
                    "column": "city",
                    "sample_source": {
                        "path": "tests/fixtures/city_country_pool.csv",
                        "column_index": 0,
                        "has_header": True,
                    },
                }
            ],
        )

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        path = tmp.name
        tmp.close()
        try:
            save_project_to_json(project, path)
            loaded = load_project_from_json(path)
            self.assertEqual(project, loaded)
        finally:
            try:
                os.remove(path)
            except PermissionError:
                pass

    def test_save_normalizes_sample_profile_fit_path_to_repo_relative(self):
        fixture_csv = Path(__file__).resolve().parent / "fixtures" / "city_country_pool.csv"
        project = SchemaProject(
            name="dg07_path_normalize",
            seed=58,
            tables=[
                TableSpec(
                    table_name="orders",
                    row_count=2,
                    columns=[
                        ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("city", "text", nullable=False),
                    ],
                )
            ],
            foreign_keys=[],
            sample_profile_fits=[
                {
                    "fit_id": "orders_city_fit",
                    "table": "orders",
                    "column": "city",
                    "sample_source": {
                        "path": str(fixture_csv),
                        "column_index": 0,
                        "has_header": True,
                    },
                }
            ],
        )

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        path = tmp.name
        tmp.close()

        try:
            save_project_to_json(project, path)
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)

            saved_path = raw["sample_profile_fits"][0]["sample_source"]["path"]
            self.assertEqual(saved_path, "tests/fixtures/city_country_pool.csv")
        finally:
            try:
                os.remove(path)
            except PermissionError:
                pass

    def test_roundtrip_preserves_locale_identity_bundles(self):
        project = SchemaProject(
            name="dg09_roundtrip",
            seed=60,
            tables=[
                TableSpec(
                    table_name="customers",
                    row_count=3,
                    columns=[
                        ColumnSpec("customer_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("locale", "text", nullable=False),
                        ColumnSpec("country_code", "text", nullable=False),
                        ColumnSpec("first_name", "text", nullable=False),
                        ColumnSpec("last_name", "text", nullable=False),
                        ColumnSpec("postcode", "text", nullable=False),
                        ColumnSpec("phone_e164", "text", nullable=False),
                        ColumnSpec("currency_code", "text", nullable=False),
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
                    "locale_weights": {"en-US": 0.7, "en-GB": 0.3},
                    "columns": {
                        "locale": "locale",
                        "country_code": "country_code",
                        "first_name": "first_name",
                        "last_name": "last_name",
                        "postcode": "postcode",
                        "phone_e164": "phone_e164",
                        "currency_code": "currency_code",
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

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        path = tmp.name
        tmp.close()
        try:
            save_project_to_json(project, path)
            loaded = load_project_from_json(path)
            self.assertEqual(project, loaded)
        finally:
            try:
                os.remove(path)
            except PermissionError:
                pass


if __name__ == "__main__":
    unittest.main()


