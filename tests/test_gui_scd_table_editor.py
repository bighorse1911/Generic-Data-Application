import tkinter as tk
import unittest

from src.config import AppConfig
from src.gui_home import App


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
        screen = self.app.screens["schema_project"]
        screen._add_table()
        idx = screen.selected_table_index
        self.assertIsNotNone(idx)
        assert idx is not None

        table_name = screen.project.tables[idx].table_name
        pk_col = f"{table_name}_id"

        self._add_non_nullable_column(screen, "segment", "text")
        self._add_non_nullable_column(screen, "city", "text")

        screen.table_business_key_var.set(pk_col)
        screen.table_scd_mode_var.set("scd1")
        screen.table_scd_tracked_columns_var.set("segment")
        screen.table_scd_active_from_var.set("")
        screen.table_scd_active_to_var.set("")
        screen._apply_table_changes()

        table = screen.project.tables[idx]
        self.assertEqual(table.business_key, [pk_col])
        self.assertEqual(table.scd_mode, "scd1")
        self.assertEqual(table.scd_tracked_columns, ["segment"])
        self.assertIsNone(table.scd_active_from_column)
        self.assertIsNone(table.scd_active_to_column)

        self._add_non_nullable_column(screen, "segment_2", "text")
        table_after = screen.project.tables[idx]
        self.assertEqual(table_after.business_key, [pk_col])
        self.assertEqual(table_after.scd_mode, "scd1")
        self.assertEqual(table_after.scd_tracked_columns, ["segment"])

    def test_kit_screen_applies_scd2_table_configuration(self):
        screen = self.app.screens["schema_project_kit"]
        screen._add_table()
        idx = screen.selected_table_index
        self.assertIsNotNone(idx)
        assert idx is not None

        self._add_non_nullable_column(screen, "customer_code", "text")
        self._add_non_nullable_column(screen, "segment", "text")
        self._add_non_nullable_column(screen, "valid_from", "date")
        self._add_non_nullable_column(screen, "valid_to", "date")

        screen.table_business_key_var.set("customer_code")
        screen.table_scd_mode_var.set("scd2")
        screen.table_scd_tracked_columns_var.set("segment")
        screen.table_scd_active_from_var.set("valid_from")
        screen.table_scd_active_to_var.set("valid_to")
        screen._apply_table_changes()

        table = screen.project.tables[idx]
        self.assertEqual(table.business_key, ["customer_code"])
        self.assertEqual(table.scd_mode, "scd2")
        self.assertEqual(table.scd_tracked_columns, ["segment"])
        self.assertEqual(table.scd_active_from_column, "valid_from")
        self.assertEqual(table.scd_active_to_column, "valid_to")


if __name__ == "__main__":
    unittest.main()
