import tkinter as tk
import unittest
from unittest import mock

from src.config import AppConfig
from src.gui_home import App
from src.gui_kit.theme import DARK_BG


class TestGuiSCDTableEditor(unittest.TestCase):
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

    def _add_non_nullable_column(self, screen, name: str, dtype: str) -> None:
        screen.col_name_var.set(name)
        screen.col_dtype_var.set(dtype)
        screen.col_nullable_var.set(False)
        screen.col_pk_var.set(False)
        screen.col_unique_var.set(False)
        screen._add_column()

    def test_legacy_screen_applies_scd1_and_preserves_fields_on_column_edit(self):
        screen = self.app.screens["schema_project_legacy"]
        screen._add_table()
        idx = screen.selected_table_index
        self.assertIsNotNone(idx)
        assert idx is not None

        table_name = screen.project.tables[idx].table_name
        pk_col = f"{table_name}_id"

        self._add_non_nullable_column(screen, "segment", "text")
        self._add_non_nullable_column(screen, "city", "text")

        screen.table_business_key_var.set(pk_col)
        screen.table_business_key_static_columns_var.set("city")
        screen.table_business_key_changing_columns_var.set("segment")
        screen.table_scd_mode_var.set("scd1")
        screen.table_scd_tracked_columns_var.set("segment")
        screen.table_scd_active_from_var.set("")
        screen.table_scd_active_to_var.set("")
        screen._apply_table_changes()

        table = screen.project.tables[idx]
        self.assertEqual(table.business_key, [pk_col])
        self.assertEqual(table.business_key_static_columns, ["city"])
        self.assertEqual(table.business_key_changing_columns, ["segment"])
        self.assertEqual(table.scd_mode, "scd1")
        self.assertEqual(table.scd_tracked_columns, ["segment"])
        self.assertIsNone(table.scd_active_from_column)
        self.assertIsNone(table.scd_active_to_column)

        self._add_non_nullable_column(screen, "segment_2", "text")
        table_after = screen.project.tables[idx]
        self.assertEqual(table_after.business_key, [pk_col])
        self.assertEqual(table_after.business_key_static_columns, ["city"])
        self.assertEqual(table_after.business_key_changing_columns, ["segment"])
        self.assertEqual(table_after.scd_mode, "scd1")
        self.assertEqual(table_after.scd_tracked_columns, ["segment"])

    def test_kit_screen_applies_scd2_table_configuration(self):
        screen = self.app.screens["schema_project_kit"]
        screen._add_table()
        idx = screen.selected_table_index
        self.assertIsNotNone(idx)
        assert idx is not None

        self._add_non_nullable_column(screen, "customer_code", "text")
        self._add_non_nullable_column(screen, "customer_name", "text")
        self._add_non_nullable_column(screen, "segment", "text")
        self._add_non_nullable_column(screen, "valid_from", "date")
        self._add_non_nullable_column(screen, "valid_to", "date")

        screen.table_business_key_var.set("customer_code")
        screen.table_business_key_static_columns_var.set("customer_name")
        screen.table_business_key_changing_columns_var.set("segment")
        screen.table_scd_mode_var.set("scd2")
        screen.table_scd_tracked_columns_var.set("segment")
        screen.table_scd_active_from_var.set("valid_from")
        screen.table_scd_active_to_var.set("valid_to")
        screen._apply_table_changes()

        table = screen.project.tables[idx]
        self.assertEqual(table.business_key, ["customer_code"])
        self.assertEqual(table.business_key_static_columns, ["customer_name"])
        self.assertEqual(table.business_key_changing_columns, ["segment"])
        self.assertEqual(table.scd_mode, "scd2")
        self.assertEqual(table.scd_tracked_columns, ["segment"])
        self.assertEqual(table.scd_active_from_column, "valid_from")
        self.assertEqual(table.scd_active_to_column, "valid_to")

    def test_kit_screen_uses_safe_threaded_job_for_long_running_actions(self):
        screen = self.app.screens["schema_project_kit"]
        screen._add_table()
        idx = screen.selected_table_index
        self.assertIsNotNone(idx)
        assert idx is not None

        table_name = screen.project.tables[idx].table_name
        pk_col = f"{table_name}_id"
        rows_payload = {table_name: [{pk_col: 1}]}

        calls: list[str] = []

        def fake_safe_job(fn, on_ok, on_err=None):
            del fn
            del on_err
            calls.append("safe_threaded_job")
            if len(calls) in {1, 2}:
                on_ok(rows_payload)
            else:
                on_ok({table_name: 1})

        with mock.patch.object(screen, "safe_threaded_job", side_effect=fake_safe_job), mock.patch(
            "src.gui_schema_project.messagebox.showinfo"
        ):
            screen._on_generate_project()
            screen._on_generate_sample()
            screen.generated_rows = rows_payload
            screen.db_path_var.set("kit_preview_test.db")
            screen._on_create_insert_sqlite()

        self.assertEqual(calls, ["safe_threaded_job", "safe_threaded_job", "safe_threaded_job"])

    def test_kit_screen_can_edit_selected_column(self):
        screen = self.app.screens["schema_project_kit"]
        screen._add_table()
        idx = screen.selected_table_index
        self.assertIsNotNone(idx)
        assert idx is not None

        self._add_non_nullable_column(screen, "old_name", "text")

        children = screen.columns_tree.get_children()
        self.assertGreaterEqual(len(children), 2)
        screen.columns_tree.selection_set(children[1])
        screen._on_column_selected()

        screen.col_name_var.set("new_name")
        screen.col_pattern_var.set("^[A-Z]+$")
        screen.col_depends_var.set(f"{screen.project.tables[idx].table_name}_id")
        screen._apply_selected_column_changes()

        table = screen.project.tables[idx]
        names = [c.name for c in table.columns]
        self.assertIn("new_name", names)
        self.assertNotIn("old_name", names)
        edited = next(c for c in table.columns if c.name == "new_name")
        self.assertEqual(edited.pattern, "^[A-Z]+$")
        self.assertEqual(edited.depends_on, [f"{table.table_name}_id"])

    def test_edit_column_requires_selected_row_with_actionable_error(self):
        screen = self.app.screens["schema_project_kit"]
        screen._add_table()
        self._add_non_nullable_column(screen, "city", "text")
        screen.columns_tree.selection_remove(screen.columns_tree.selection())

        with mock.patch("src.gui_schema_project.messagebox.showerror") as showerror:
            screen._apply_selected_column_changes()
            showerror.assert_called_once()
            title, message = showerror.call_args.args

        self.assertEqual(title, "Edit column failed")
        self.assertIn("Edit column", message)
        self.assertIn("no column is selected", message)
        self.assertIn("Fix:", message)

    def test_kit_screen_applies_dark_mode(self):
        screen = self.app.screens["schema_project_kit"]
        self.assertTrue(getattr(screen, "kit_dark_mode_enabled", False))
        self.assertEqual(str(screen.scroll.canvas.cget("background")).lower(), DARK_BG.lower())


if __name__ == "__main__":
    unittest.main()
