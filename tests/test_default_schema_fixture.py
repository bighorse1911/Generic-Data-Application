import json
import os
import re
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from src.generator_project import generate_project_rows
from src.schema_project_io import load_project_from_json


class TestDefaultSchemaFixture(unittest.TestCase):
    def _load_fixture_project(self):
        fixtures_dir = Path(__file__).resolve().parent / "fixtures"
        json_path = fixtures_dir / "default_schema_project.json"
        csv_path = fixtures_dir / "city_country_pool.csv"

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for table in data.get("tables", []):
            for col in table.get("columns", []):
                params = col.get("params")
                if isinstance(params, dict) and params.get("path") == "__CITY_COUNTRY_CSV__":
                    params["path"] = str(csv_path)

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        temp_json_path = tmp.name
        tmp.close()

        with open(temp_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        try:
            project = load_project_from_json(temp_json_path)
            return project
        finally:
            try:
                os.remove(temp_json_path)
            except PermissionError:
                pass

    def test_fixture_generates_deterministically_and_covers_behaviors(self):
        project = self._load_fixture_project()

        rows_a = generate_project_rows(project)
        rows_b = generate_project_rows(project)

        self.assertEqual(rows_a, rows_b)

        self.assertEqual(set(rows_a.keys()), {"customers", "campaigns", "orders", "events"})
        self.assertEqual(len(rows_a["customers"]), 12)
        self.assertEqual(len(rows_a["campaigns"]), 5)
        self.assertGreaterEqual(len(rows_a["orders"]), 12)
        self.assertLessEqual(len(rows_a["orders"]), 36)
        self.assertEqual(len(rows_a["events"]), 20)

        for table_name, pk_col in [
            ("customers", "customer_id"),
            ("campaigns", "campaign_id"),
            ("orders", "order_id"),
            ("events", "event_id"),
        ]:
            values = [r.get(pk_col) for r in rows_a[table_name]]
            self.assertTrue(
                all(v is not None for v in values),
                f"Fixture invariant failed at table '{table_name}', column '{pk_col}': PK contains nulls. "
                "Fix: keep PK generation non-null for every row.",
            )
            self.assertEqual(
                len(values),
                len(set(values)),
                f"Fixture invariant failed at table '{table_name}', column '{pk_col}': PK contains duplicates. "
                "Fix: keep PK generation unique per table.",
            )

        customer_ids = {r["customer_id"] for r in rows_a["customers"]}
        campaign_ids = {r["campaign_id"] for r in rows_a["campaigns"]}

        for order in rows_a["orders"]:
            self.assertIn(order["customer_id"], customer_ids)

        for event in rows_a["events"]:
            self.assertIn(event["customer_id"], customer_ids)
            self.assertIn(event["campaign_id"], campaign_ids)

        fixture_csv = Path(__file__).resolve().parent / "fixtures" / "city_country_pool.csv"
        with open(fixture_csv, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines()[1:] if line.strip()]
        known_cities = {line.split(",")[0] for line in lines}
        known_countries = {line.split(",")[1] for line in lines}

        for row in rows_a["customers"]:
            self.assertGreaterEqual(row["age"], 18)
            self.assertLessEqual(row["age"], 75)
            self.assertGreaterEqual(row["salary"], 25000)
            self.assertLessEqual(row["salary"], 200000)

            self.assertIn(row["segment"], {"A", "B", "C"})
            self.assertIn(row["home_city"], known_cities)
            self.assertIn(row["home_country"], known_countries)

            date.fromisoformat(row["signup_date"])
            signup_ts = datetime.fromisoformat(row["signup_ts"].replace("Z", "+00:00"))
            self.assertEqual(signup_ts.tzinfo, timezone.utc)

            self.assertIn(row["active"], {0, 1})
            self.assertGreaterEqual(row["latitude"], 37.0)
            self.assertLessEqual(row["latitude"], 38.0)
            self.assertGreaterEqual(row["longitude"], -123.0)
            self.assertLessEqual(row["longitude"], -121.0)

            self.assertGreaterEqual(row["score"], 0.0)
            self.assertLessEqual(row["score"], 100.0)
            self.assertGreaterEqual(row["lifetime_value"], 100.0)
            self.assertLessEqual(row["lifetime_value"], 25000.0)

            self.assertRegex(row["note"], re.compile(r"^[a-z]{5,14}$"))
            self.assertIn(row["optional_tag"], {None, "alpha", "beta", "gamma"})

            self.assertEqual(row["outlier_metric"], 100.0)

            self.assertGreaterEqual(row["fallback_int"], 1)
            self.assertLessEqual(row["fallback_int"], 5)
            self.assertGreaterEqual(row["fallback_float"], 0.5)
            self.assertLessEqual(row["fallback_float"], 2.5)
            date.fromisoformat(row["fallback_date"])
            fallback_ts = datetime.fromisoformat(row["fallback_datetime"].replace("Z", "+00:00"))
            self.assertEqual(fallback_ts.tzinfo, timezone.utc)

            self.assertIn(row["status_choice"], {"new", "returning", "vip"})

        for row in rows_a["campaigns"]:
            self.assertIn(row["channel"], {"email", "sms", "push"})
            self.assertGreaterEqual(row["budget"], 1000.0)
            self.assertLessEqual(row["budget"], 5000.0)
            date.fromisoformat(row["started_on"])
            date.fromisoformat(row["ended_on"])
            self.assertIn(row["active"], {0, 1})

        for row in rows_a["orders"]:
            order_ts = datetime.fromisoformat(row["ordered_at"].replace("Z", "+00:00"))
            self.assertEqual(order_ts.tzinfo, timezone.utc)
            self.assertGreaterEqual(row["order_amount"], 1.0)
            self.assertLessEqual(row["order_amount"], 2000.0)
            self.assertIn(row["order_status"], {"NEW", "PAID", "SHIPPED"})

        for row in rows_a["events"]:
            event_ts = datetime.fromisoformat(row["event_time"].replace("Z", "+00:00"))
            self.assertEqual(event_ts.tzinfo, timezone.utc)
            self.assertIn(row["event_type"], {"impression", "click", "purchase"})
            self.assertGreaterEqual(row["event_amount"], 1.0)
            self.assertLessEqual(row["event_amount"], 500.0)
            self.assertGreaterEqual(row["event_lat"], 30.0)
            self.assertLessEqual(row["event_lat"], 50.0)
            self.assertGreaterEqual(row["event_lon"], -130.0)
            self.assertLessEqual(row["event_lon"], -60.0)
            self.assertGreaterEqual(row["quality_score"], 0.0)
            self.assertLessEqual(row["quality_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
