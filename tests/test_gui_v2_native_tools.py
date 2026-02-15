import tkinter as tk
import unittest

from src.config import AppConfig
from src.gui_home import App
from src.gui_home import GENERATION_BEHAVIOR_GUIDE


class TestGuiV2NativeTools(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk GUI not available in this environment: {exc}")
            return
        self.root.withdraw()
        self.app = App(self.root, AppConfig())

    def tearDown(self):
        if hasattr(self, "root") and self.root.winfo_exists():
            self.root.destroy()

    def test_generation_guide_v2_renders_canonical_entries(self):
        screen = self.app.screens["generation_behaviors_guide_v2"]
        tool = screen.tool
        cards = tool.scroll.content.winfo_children()
        self.assertEqual(len(cards), len(GENERATION_BEHAVIOR_GUIDE))
        self.assertIn("sample_csv generator", {entry[0] for entry in GENERATION_BEHAVIOR_GUIDE})

    def test_location_selector_v2_builds_geojson_and_deterministic_points(self):
        screen = self.app.screens["location_selector_v2"]
        tool = screen.tool

        tool.center_lat_var.set("37.7749")
        tool.center_lon_var.set("-122.4194")
        tool._set_center_from_fields()

        tool.radius_km_var.set("25")
        tool.geojson_steps_var.set("48")
        tool._build_geojson()
        geojson_text = tool.geojson_text.get("1.0", "end")
        self.assertIn('"type": "Feature"', geojson_text)

        tool.sample_count_var.set("12")
        tool.sample_seed_var.set("999")
        tool._generate_points()
        first_run = list(tool._latest_points)
        self.assertEqual(len(first_run), 12)

        tool._generate_points()
        second_run = list(tool._latest_points)
        self.assertEqual(first_run, second_run)

    def test_erd_designer_v2_supports_authoring_flow(self):
        screen = self.app.screens["erd_designer_v2"]
        tool = screen.tool

        tool.schema_name_var.set("native_v2_erd")
        tool.schema_seed_var.set("123")
        tool._create_new_schema()
        self.assertIsNotNone(tool.project)

        tool.table_name_var.set("customers")
        tool._add_table()
        tool.table_name_var.set("orders")
        tool._add_table()

        tool.column_table_var.set("customers")
        tool.column_name_var.set("customer_id")
        tool.column_dtype_var.set("int")
        tool.column_primary_key_var.set(True)
        tool._on_column_pk_changed()
        tool._add_column()

        tool.column_table_var.set("orders")
        tool.column_name_var.set("order_id")
        tool.column_dtype_var.set("int")
        tool.column_primary_key_var.set(True)
        tool._on_column_pk_changed()
        tool._add_column()

        tool.column_table_var.set("orders")
        tool.column_name_var.set("customer_id")
        tool.column_dtype_var.set("int")
        tool.column_primary_key_var.set(False)
        tool.column_nullable_var.set(False)
        tool._on_column_pk_changed()
        tool._add_column()

        tool.relationship_child_table_var.set("orders")
        tool._on_relationship_child_table_changed()
        tool.relationship_child_column_var.set("customer_id")
        tool.relationship_parent_table_var.set("customers")
        tool._on_relationship_parent_table_changed()
        tool.relationship_parent_column_var.set("customer_id")
        tool.relationship_min_children_var.set("1")
        tool.relationship_max_children_var.set("3")
        tool._add_relationship()

        self.assertEqual(len(tool.project.foreign_keys), 1)


if __name__ == "__main__":
    unittest.main()
