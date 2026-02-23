import tkinter as tk
import unittest

from src.config import AppConfig
from src.gui_home import App
from src.gui_route_policy import SCHEMA_V2_ROUTE


class TestGuiUndoRedo(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk GUI not available in this environment: {exc}")
            return
        self.root.withdraw()
        self.app = App(self.root, AppConfig())
        self.screen = self.app.screens[SCHEMA_V2_ROUTE]

    def tearDown(self) -> None:
        if hasattr(self, "root") and self.root.winfo_exists():
            self.root.destroy()

    def _select_table(self, index: int) -> None:
        self.screen.tables_list.selection_clear(0, tk.END)
        self.screen.tables_list.selection_set(index)
        self.screen.tables_list.activate(index)
        self.screen.tables_list.see(index)
        self.screen._on_table_selected()

    def _ensure_table(self) -> None:
        if not self.screen.project.tables:
            self.screen._add_table()
        if self.screen.selected_table_index is None:
            self._select_table(0)

    def test_undo_redo_add_table(self) -> None:
        baseline_count = len(self.screen.project.tables)
        self.assertFalse(self.screen.undo_stack.can_undo)

        self.screen._add_table()
        self.assertEqual(len(self.screen.project.tables), baseline_count + 1)
        self.assertTrue(self.screen.undo_stack.can_undo)

        self.screen._undo_last_change()
        self.assertEqual(len(self.screen.project.tables), baseline_count)
        self.assertFalse(self.screen.is_dirty)

        self.screen._redo_last_change()
        self.assertEqual(len(self.screen.project.tables), baseline_count + 1)
        self.assertTrue(self.screen.is_dirty)

    def test_undo_redo_table_scd_edit(self) -> None:
        self._ensure_table()
        idx = self.screen.selected_table_index
        assert idx is not None
        table_name = self.screen.project.tables[idx].table_name
        pk_name = f"{table_name}_id"

        self.screen.col_name_var.set("segment")
        self.screen.col_dtype_var.set("text")
        self.screen.col_nullable_var.set(False)
        self.screen.col_pk_var.set(False)
        self.screen._add_column()

        self.screen.table_business_key_var.set(pk_name)
        self.screen.table_business_key_changing_columns_var.set("segment")
        self.screen.table_scd_mode_var.set("scd1")
        self.screen.table_scd_tracked_columns_var.set("segment")
        self.screen._apply_table_changes()

        edited = self.screen.project.tables[idx]
        self.assertEqual(edited.scd_mode, "scd1")
        self.assertEqual(edited.scd_tracked_columns, ["segment"])
        self.assertEqual(edited.business_key_changing_columns, ["segment"])

        self.screen._undo_last_change()
        reverted = self.screen.project.tables[idx]
        self.assertIsNone(reverted.scd_mode)
        self.assertIsNone(reverted.scd_tracked_columns)
        self.assertIsNone(reverted.business_key_changing_columns)

        self.screen._redo_last_change()
        reapplied = self.screen.project.tables[idx]
        self.assertEqual(reapplied.scd_mode, "scd1")
        self.assertEqual(reapplied.scd_tracked_columns, ["segment"])
        self.assertEqual(reapplied.business_key_changing_columns, ["segment"])

    def test_undo_redo_fk_add(self) -> None:
        self.screen._add_table()
        parent_index = self.screen.selected_table_index
        assert parent_index is not None
        parent_table = self.screen.project.tables[parent_index].table_name

        self.screen._add_table()
        child_index = self.screen.selected_table_index
        assert child_index is not None
        child_table = self.screen.project.tables[child_index].table_name

        self.screen.col_name_var.set(f"{parent_table}_id")
        self.screen.col_dtype_var.set("int")
        self.screen.col_nullable_var.set(False)
        self.screen.col_pk_var.set(False)
        self.screen._add_column()

        self.screen.fk_parent_table_var.set(parent_table)
        self.screen.fk_child_table_var.set(child_table)
        self.screen.fk_child_column_var.set(f"{parent_table}_id")
        self.screen.fk_min_children_var.set("1")
        self.screen.fk_max_children_var.set("2")
        self.screen._add_fk()
        self.assertEqual(len(self.screen.project.foreign_keys), 1)

        self.screen._undo_last_change()
        self.assertEqual(len(self.screen.project.foreign_keys), 0)

        self.screen._redo_last_change()
        self.assertEqual(len(self.screen.project.foreign_keys), 1)


if __name__ == "__main__":
    unittest.main()
