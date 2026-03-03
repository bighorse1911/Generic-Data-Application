from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date

from src.generator_project import generate_project_rows, generate_project_rows_streaming
from src.schema_project_model import ColumnSpec, ForeignKeySpec, SchemaProject, TableSpec, validate_project


class PipelineParityContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fd, path = tempfile.mkstemp(prefix="dg07_parity_", suffix=".csv", text=True)
        os.close(fd)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("score\n")
            f.write("10.0\n")
            f.write("20.0\n")
            f.write("35.5\n")
            f.write("42.0\n")
            f.write("64.25\n")
        cls._sample_csv_path = path

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            os.remove(cls._sample_csv_path)
        except OSError:
            pass

    @classmethod
    def _fk_timeline_quality_locale_correlation_project(cls) -> SchemaProject:
        return SchemaProject(
            name="pipeline_parity_fk_timeline_quality_locale_corr",
            seed=20260301,
            tables=[
                TableSpec(
                    table_name="customers",
                    row_count=30,
                    columns=[
                        ColumnSpec("customer_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "segment",
                            "text",
                            nullable=False,
                            generator="choice_weighted",
                            params={"choices": ["VIP", "STD"], "weights": [1.0, 1.0]},
                        ),
                        ColumnSpec(
                            "signup_date",
                            "date",
                            nullable=False,
                            generator="date",
                            params={"start": "2024-01-01", "end": "2024-01-30"},
                        ),
                        ColumnSpec(
                            "engagement_score",
                            "decimal",
                            nullable=False,
                            generator="normal",
                            params={"mean": 55.0, "stdev": 12.0, "min": 0.0, "max": 100.0, "decimals": 2},
                        ),
                        ColumnSpec(
                            "spend_score",
                            "decimal",
                            nullable=False,
                            generator="normal",
                            params={"mean": 600.0, "stdev": 140.0, "min": 100.0, "max": 1200.0, "decimals": 2},
                        ),
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
                    correlation_groups=[
                        {
                            "group_id": "customer_corr",
                            "columns": ["engagement_score", "spend_score", "segment"],
                            "rank_correlation": [
                                [1.0, 0.75, 0.45],
                                [0.75, 1.0, 0.40],
                                [0.45, 0.40, 1.0],
                            ],
                            "categorical_orders": {"segment": ["STD", "VIP"]},
                            "strength": 1.0,
                        }
                    ],
                ),
                TableSpec(
                    table_name="orders",
                    row_count=90,
                    columns=[
                        ColumnSpec("order_id", "int", nullable=False, primary_key=True),
                        ColumnSpec("customer_id", "int", nullable=False),
                        ColumnSpec(
                            "ordered_on",
                            "date",
                            nullable=False,
                            generator="date",
                            params={"start": "2024-02-01", "end": "2024-03-15"},
                        ),
                        ColumnSpec(
                            "ship_on",
                            "date",
                            nullable=False,
                            generator="time_offset",
                            params={
                                "base_column": "ordered_on",
                                "direction": "after",
                                "min_days": 1,
                                "max_days": 7,
                            },
                            depends_on=["ordered_on"],
                        ),
                        ColumnSpec(
                            "status",
                            "text",
                            nullable=True,
                            generator="choice_weighted",
                            params={"choices": ["OK", "HOLD"], "weights": [4.0, 1.0]},
                        ),
                        ColumnSpec(
                            "order_value",
                            "decimal",
                            nullable=False,
                            generator="uniform_float",
                            params={"min": 50.0, "max": 500.0, "decimals": 2},
                        ),
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
                    max_children=4,
                    parent_selection={
                        "parent_attribute": "segment",
                        "weights": {"VIP": 6.0, "STD": 1.0},
                        "default_weight": 1.0,
                    },
                    child_count_distribution={"type": "poisson", "lambda": 1.4},
                )
            ],
            timeline_constraints=[
                {
                    "rule_id": "ordered_after_signup",
                    "child_table": "orders",
                    "child_column": "ordered_on",
                    "references": [
                        {
                            "parent_table": "customers",
                            "parent_column": "signup_date",
                            "via_child_fk": "customer_id",
                            "direction": "after",
                            "min_days": 0,
                            "max_days": 90,
                        }
                    ],
                }
            ],
            data_quality_profiles=[
                {
                    "profile_id": "status_missing",
                    "table": "orders",
                    "column": "status",
                    "kind": "missingness",
                    "mechanism": "mnar",
                    "base_rate": 0.2,
                    "value_weights": {"HOLD": 3.0, "OK": 0.5},
                    "default_weight": 0.5,
                },
                {
                    "profile_id": "value_drift",
                    "table": "orders",
                    "column": "order_value",
                    "kind": "quality_issue",
                    "issue_type": "drift",
                    "rate": 1.0,
                    "step": 0.25,
                    "start_index": 1,
                },
            ],
            locale_identity_bundles=[
                {
                    "bundle_id": "customer_identity",
                    "base_table": "customers",
                    "locale_weights": {"en-US": 0.7, "fr-FR": 0.3},
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
                            "columns": {"locale": "locale", "currency_code": "currency_code"},
                        }
                    ],
                }
            ],
        )

    @classmethod
    def _scd_and_profile_fit_project(cls) -> SchemaProject:
        return SchemaProject(
            name="pipeline_parity_scd_profile_fit",
            seed=20260302,
            tables=[
                TableSpec(
                    table_name="customer_dim",
                    row_count=12,
                    columns=[
                        ColumnSpec("customer_sk", "int", nullable=False, primary_key=True),
                        ColumnSpec("customer_code", "text", nullable=False),
                        ColumnSpec(
                            "city",
                            "text",
                            nullable=False,
                            generator="choice_weighted",
                            params={"choices": ["Austin", "Boston", "Chicago"], "weights": [2.0, 1.0, 1.0]},
                        ),
                        ColumnSpec("score", "decimal", nullable=False),
                        ColumnSpec("valid_from", "date", nullable=False),
                        ColumnSpec("valid_to", "date", nullable=False),
                    ],
                    business_key=["customer_code"],
                    business_key_unique_count=6,
                    business_key_static_columns=["customer_code"],
                    business_key_changing_columns=["city", "score"],
                    scd_mode="scd2",
                    scd_tracked_columns=["city", "score"],
                    scd_active_from_column="valid_from",
                    scd_active_to_column="valid_to",
                )
            ],
            foreign_keys=[],
            sample_profile_fits=[
                {
                    "fit_id": "score_fit",
                    "table": "customer_dim",
                    "column": "score",
                    "sample_source": {
                        "path": cls._sample_csv_path,
                        "column_name": "score",
                        "has_header": True,
                    },
                }
            ],
        )

    def _stream_rows(self, project: SchemaProject) -> dict[str, list[dict[str, object]]]:
        out: dict[str, list[dict[str, object]]] = {}

        def _capture(table_name: str, rows: list[dict[str, object]]) -> None:
            out[table_name] = rows

        generate_project_rows_streaming(project, on_table_rows=_capture)
        return out

    def test_batch_generation_is_deterministic(self) -> None:
        for project in (
            self._fk_timeline_quality_locale_correlation_project(),
            self._scd_and_profile_fit_project(),
        ):
            validate_project(project)
            rows_a = generate_project_rows(project)
            rows_b = generate_project_rows(project)
            self.assertEqual(rows_a, rows_b)

    def test_streaming_matches_batch(self) -> None:
        for project in (
            self._fk_timeline_quality_locale_correlation_project(),
            self._scd_and_profile_fit_project(),
        ):
            validate_project(project)
            batch = generate_project_rows(project)
            streamed = self._stream_rows(project)
            self.assertEqual(batch, streamed)

    def test_key_invariants_for_fk_timeline_locale_and_scd(self) -> None:
        fk_project = self._fk_timeline_quality_locale_correlation_project()
        validate_project(fk_project)
        fk_rows = generate_project_rows(fk_project)

        customers = fk_rows["customers"]
        orders = fk_rows["orders"]
        by_customer_id = {int(row["customer_id"]): row for row in customers}
        counts_by_customer: dict[int, int] = {customer_id: 0 for customer_id in by_customer_id}
        for order in orders:
            customer_id = int(order["customer_id"])
            counts_by_customer[customer_id] += 1

            parent = by_customer_id[customer_id]
            self.assertEqual(order["locale"], parent["locale"])
            self.assertEqual(order["currency_code"], parent["currency_code"])

            ordered_on = date.fromisoformat(str(order["ordered_on"]))
            signup = date.fromisoformat(str(parent["signup_date"]))
            self.assertGreaterEqual(ordered_on, signup)
            self.assertLessEqual((ordered_on - signup).days, 90)

        self.assertEqual(len(counts_by_customer), 30)
        self.assertTrue(all(1 <= count <= 4 for count in counts_by_customer.values()))

        scd_project = self._scd_and_profile_fit_project()
        validate_project(scd_project)
        scd_rows = generate_project_rows(scd_project)["customer_dim"]
        by_key: dict[str, list[dict[str, object]]] = {}
        for row in scd_rows:
            by_key.setdefault(str(row["customer_code"]), []).append(row)

        self.assertEqual(len(by_key), 6)
        for key_rows in by_key.values():
            ordered = sorted(key_rows, key=lambda row: str(row["valid_from"]))
            for idx in range(len(ordered) - 1):
                prev_to = date.fromisoformat(str(ordered[idx]["valid_to"]))
                next_from = date.fromisoformat(str(ordered[idx + 1]["valid_from"]))
                self.assertLess(prev_to, next_from)
            self.assertEqual(str(ordered[-1]["valid_to"]), "9999-12-31")


if __name__ == "__main__":
    unittest.main()
