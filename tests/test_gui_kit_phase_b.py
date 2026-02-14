import tkinter as tk
import unittest
from unittest import mock

from src.config import AppConfig
from src.gui_home import App
from src.gui_kit.column_chooser import normalize_column_preferences
from src.gui_kit.validation import InlineValidationEntry
from src.gui_schema_project import ValidationIssue


class TestGUIKitPhaseB(unittest.TestCase):
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

    def test_normalize_column_preferences_keeps_schema_order_for_unlisted_columns(self):
        rows = normalize_column_preferences(
            ["id", "name", "region", "status"],
            visible_columns=["status", "id"],
        )
        self.assertEqual(
            rows,
            [
                ("status", True),
                ("id", True),
                ("name", False),
                ("region", False),
            ],
        )

    def test_kit_screen_dirty_guard_marks_dirty_and_cleans_on_save(self):
        screen = self.app.screens["schema_project"]
        self.assertFalse(screen.is_dirty)
        screen._add_table()
        self.assertTrue(screen.is_dirty)

        with mock.patch(
            "src.gui_schema_project.filedialog.asksaveasfilename",
            return_value="phase_b_test_project.json",
        ), mock.patch("src.gui_schema_project.save_project_to_json"):
            saved = screen._save_project()

        self.assertTrue(saved)
        self.assertFalse(screen.is_dirty)

    def test_kit_screen_back_navigation_respects_dirty_prompt(self):
        screen = self.app.screens["schema_project"]
        screen._add_table()
        self.assertTrue(screen.is_dirty)

        with mock.patch("src.gui_kit.layout.messagebox.askyesnocancel", return_value=None), mock.patch.object(
            screen.app, "go_home"
        ) as go_home:
            screen._on_back_requested()
            go_home.assert_not_called()

        with mock.patch("src.gui_kit.layout.messagebox.askyesnocancel", return_value=False), mock.patch.object(
            screen.app, "go_home"
        ) as go_home:
            screen._on_back_requested()
            go_home.assert_called_once()

    def test_kit_screen_inline_validation_summary_is_populated(self):
        screen = self.app.screens["schema_project"]
        screen._run_validation()
        self.assertGreaterEqual(len(screen.inline_validation.tree.get_children()), 1)

    def test_kit_screen_validation_jump_selects_table_and_column(self):
        screen = self.app.screens["schema_project"]
        screen._add_table()
        table = screen.project.tables[0].table_name
        column = f"{table}_id"
        issue = ValidationIssue(
            severity="error",
            scope="column",
            table=table,
            column=column,
            message="test issue",
        )
        entry = InlineValidationEntry(
            severity="error",
            location=f"Table '{table}', column '{column}'",
            message="test issue",
            jump_payload=issue,
        )

        screen._jump_to_validation_issue(entry)
        self.assertEqual(screen.selected_table_index, 0)
        selected = screen.columns_tree.selection()
        self.assertEqual(len(selected), 1)
        values = screen.columns_tree.item(selected[0], "values")
        self.assertEqual(str(values[0]), column)


if __name__ == "__main__":
    unittest.main()
