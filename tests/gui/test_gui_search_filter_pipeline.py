from dataclasses import replace
import tkinter as tk
import unittest

from src.config import AppConfig
from src.gui_home import App
from src.gui_route_policy import SCHEMA_V2_ROUTE
from src.schema_project_model import ColumnSpec, ForeignKeySpec, TableSpec


class TestGuiSearchFilterPipeline(unittest.TestCase):
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

    def _ensure_table(self) -> None:
        if not self.screen.project.tables:
            self.screen._add_table()
        self.screen.selected_table_index = 0

    def test_columns_filter_is_paged_and_preserves_source_index(self) -> None:
        self._ensure_table()
        table = self.screen.project.tables[0]
        cols = [
            ColumnSpec(name=f"column_{idx}", dtype="text", nullable=True, primary_key=False)
            for idx in range(450)
        ]
        self.screen.project = replace(self.screen.project, tables=[replace(table, columns=cols)])
        self.screen._refresh_columns_tree()

        self.assertEqual(len(self.screen.columns_tree.get_children()), 200)
        self.assertIn("page 1/3", self.screen.columns_page_var.get())

        self.screen._on_columns_filter_next_page()
        second_page = list(self.screen.columns_tree.get_children())
        self.assertEqual(len(second_page), 200)
        self.assertIn("page 2/3", self.screen.columns_page_var.get())

        self.screen.columns_tree.selection_set(second_page[0])
        self.assertEqual(self.screen._selected_column_index(), 200)

        self.screen._on_columns_search_change("column_449")
        visible = list(self.screen.columns_tree.get_children())
        self.assertEqual(len(visible), 1)
        values = self.screen.columns_tree.item(visible[0], "values")
        self.assertEqual(str(values[0]), "column_449")

    def test_fk_filter_is_paged_and_preserves_source_index(self) -> None:
        parent = TableSpec(
            table_name="parent",
            row_count=10,
            columns=[ColumnSpec(name="parent_id", dtype="int", nullable=False, primary_key=True)],
        )
        child = TableSpec(
            table_name="child",
            row_count=10,
            columns=[
                ColumnSpec(name="child_id", dtype="int", nullable=False, primary_key=True),
                ColumnSpec(name="parent_id", dtype="int", nullable=False, primary_key=False),
            ],
        )
        fks = [
            ForeignKeySpec(
                child_table="child",
                child_column=f"fk_{idx}",
                parent_table="parent",
                parent_column="parent_id",
                min_children=1,
                max_children=2,
            )
            for idx in range(350)
        ]
        self.screen.project = replace(self.screen.project, tables=[parent, child], foreign_keys=fks)
        self.screen._refresh_fks_tree()

        self.assertEqual(len(self.screen.fks_tree.get_children()), 200)
        self.assertIn("page 1/2", self.screen.fks_page_var.get())

        self.screen._on_fk_filter_next_page()
        second_page = list(self.screen.fks_tree.get_children())
        self.assertEqual(len(second_page), 150)
        self.assertIn("page 2/2", self.screen.fks_page_var.get())

        self.screen.fks_tree.selection_set(second_page[0])
        self.assertEqual(self.screen._selected_fk_index(), 200)

        self.screen._on_fk_search_change("fk_349")
        visible = list(self.screen.fks_tree.get_children())
        self.assertEqual(len(visible), 1)
        values = self.screen.fks_tree.item(visible[0], "values")
        self.assertEqual(str(values[3]), "fk_349")


if __name__ == "__main__":
    unittest.main()
