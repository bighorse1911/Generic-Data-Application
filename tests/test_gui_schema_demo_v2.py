import os
import tempfile
import tkinter as tk
import unittest
from unittest import mock

from src.config import AppConfig
from src.gui_home import App
from src.gui_route_policy import SCHEMA_DEMO_V2_ROUTE
from src.gui_route_policy import SCHEMA_V2_ROUTE


class TestGuiSchemaDemoV2(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk GUI not available in this environment: {exc}")
            return
        self.root.withdraw()
        self.app = App(self.root, AppConfig())

    def tearDown(self) -> None:
        if hasattr(self, "root") and self.root.winfo_exists():
            self.root.destroy()

    def _select_table(self, screen, table_name: str) -> None:
        for idx, table in enumerate(screen.project.tables):
            if table.table_name != table_name:
                continue
            screen.tables_list.selection_clear(0, tk.END)
            screen.tables_list.selection_set(idx)
            screen.tables_list.activate(idx)
            screen.tables_list.see(idx)
            screen._on_table_selected()
            return
        self.fail(f"Table '{table_name}' not found in demo project.")

    def _find_fk_tree_item(self, screen, child_table: str, child_column: str) -> str | None:
        for item in screen.fks_tree.get_children():
            values = screen.fks_tree.item(item, "values")
            if len(values) < 4:
                continue
            if str(values[2]) == child_table and str(values[3]) == child_column:
                return str(item)
        return None

    def test_route_registration_and_navigation(self) -> None:
        self.assertIn(SCHEMA_DEMO_V2_ROUTE, self.app.screens)
        self.app.show_screen(SCHEMA_DEMO_V2_ROUTE)
        self.assertEqual(self.app.current_screen_name, SCHEMA_DEMO_V2_ROUTE)

    def test_demo_preload_defaults_to_orders_with_preview_rows(self) -> None:
        self.app.show_screen(SCHEMA_DEMO_V2_ROUTE)
        screen = self.app.screens[SCHEMA_DEMO_V2_ROUTE]

        self.assertTrue(screen._demo_seeded)
        self.assertEqual(screen.table_name_var.get(), "orders")
        self.assertEqual(screen.preview_table_var.get(), "orders")
        self.assertGreater(len(screen.preview_tree.get_children()), 0)

    def test_add_remove_column_and_add_remove_fk_use_real_callbacks(self) -> None:
        self.app.show_screen(SCHEMA_DEMO_V2_ROUTE)
        screen = self.app.screens[SCHEMA_DEMO_V2_ROUTE]

        self._select_table(screen, "shipments")
        before_cols = len(screen.project.tables[screen.selected_table_index].columns)
        before_fks = len(screen.project.foreign_keys)

        screen.col_name_var.set("customer_id")
        screen.col_dtype_var.set("int")
        screen.col_nullable_var.set(False)
        screen.col_pk_var.set(False)
        screen.col_unique_var.set(False)
        screen._add_column()
        self.assertEqual(len(screen.project.tables[screen.selected_table_index].columns), before_cols + 1)

        screen.fk_parent_table_var.set("customers")
        screen.fk_child_table_var.set("shipments")
        screen.fk_child_column_var.set("customer_id")
        screen.fk_min_children_var.set("1")
        screen.fk_max_children_var.set("2")
        screen._add_fk()
        self.assertEqual(len(screen.project.foreign_keys), before_fks + 1)

        fk_item = self._find_fk_tree_item(screen, "shipments", "customer_id")
        self.assertIsNotNone(fk_item)
        assert fk_item is not None
        screen.fks_tree.selection_set(fk_item)
        screen._remove_selected_fk()
        self.assertEqual(len(screen.project.foreign_keys), before_fks)

        for item in screen.columns_tree.get_children():
            values = screen.columns_tree.item(item, "values")
            if len(values) > 0 and str(values[0]) == "customer_id":
                screen.columns_tree.selection_set(item)
                screen.columns_tree.focus(item)
                break
        screen._remove_selected_column()
        self.assertEqual(len(screen.project.tables[screen.selected_table_index].columns), before_cols)

    def test_mock_data_and_distribution_buttons_open_constraints_targets(self) -> None:
        self.app.show_screen(SCHEMA_DEMO_V2_ROUTE)
        screen = self.app.screens[SCHEMA_DEMO_V2_ROUTE]

        screen.mock_rules_btn.invoke()
        self.assertEqual(str(screen.details_tabs.select()), str(screen.constraints_tab))
        self.assertFalse(screen.constraints_rules_panel.is_collapsed)

        screen.distribution_btn.invoke()
        self.assertEqual(str(screen.details_tabs.select()), str(screen.constraints_tab))
        self.assertFalse(screen.constraints_distribution_panel.is_collapsed)

    def test_generate_save_and_close_actions(self) -> None:
        self.app.show_screen(SCHEMA_DEMO_V2_ROUTE)
        screen = self.app.screens[SCHEMA_DEMO_V2_ROUTE]

        with mock.patch.object(screen.job_lifecycle, "run_async") as run_async:
            screen.generate_btn.invoke()
            run_async.assert_called_once()

        with tempfile.TemporaryDirectory() as tmp_dir:
            save_path = os.path.join(tmp_dir, "schema_demo_v2_save.json")
            with mock.patch("src.gui_schema_project.filedialog.asksaveasfilename", return_value=save_path):
                saved = bool(screen._save_project())
            self.assertTrue(saved)
            self.assertTrue(os.path.exists(save_path))

        with mock.patch.object(screen, "confirm_discard_or_save", return_value=True):
            screen.close_btn.invoke()
        self.assertEqual(self.app.current_screen_name, "home_v2")

    def test_demo_route_state_is_independent_from_schema_project_v2(self) -> None:
        self.app.show_screen(SCHEMA_DEMO_V2_ROUTE)
        demo = self.app.screens[SCHEMA_DEMO_V2_ROUTE]
        demo.project_name_var.set("demo_route_only")

        schema_v2 = self.app.screens[SCHEMA_V2_ROUTE]
        self.assertNotEqual(schema_v2.project_name_var.get(), "demo_route_only")

        self.app.show_screen(SCHEMA_V2_ROUTE)
        schema_v2.project_name_var.set("schema_v2_only")

        self.app.show_screen(SCHEMA_DEMO_V2_ROUTE)
        self.assertEqual(demo.project_name_var.get(), "demo_route_only")
        self.assertNotEqual(demo.project_name_var.get(), schema_v2.project_name_var.get())


if __name__ == "__main__":
    unittest.main()
