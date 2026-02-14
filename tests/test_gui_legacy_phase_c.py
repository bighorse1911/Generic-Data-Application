import tkinter as tk
import unittest
from unittest import mock

from src.config import AppConfig
from src.gui_home import App
from src.gui_kit.validation import InlineValidationEntry
from src.gui_schema_project import ValidationIssue


class TestGuiLegacyPhaseC(unittest.TestCase):
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

    def test_legacy_screen_exposes_phase_c_widgets(self):
        screen = self.app.screens["schema_project_legacy"]
        self.assertTrue(hasattr(screen, "inline_validation"))
        self.assertTrue(hasattr(screen, "preview_table"))
        self.assertTrue(hasattr(screen, "preview_columns_btn"))
        self.assertTrue(hasattr(screen, "preview_paging_chk"))

    def test_legacy_preview_paging_toggle_is_opt_in(self):
        screen = self.app.screens["schema_project_legacy"]
        self.assertFalse(screen.preview_paging_enabled_var.get())
        self.assertFalse(screen.preview_table._pagination_enabled)
        screen.preview_paging_enabled_var.set(True)
        screen._on_preview_paging_toggled()
        self.assertTrue(screen.preview_table._pagination_enabled)

    def test_legacy_dirty_guard_blocks_back_on_cancel(self):
        screen = self.app.screens["schema_project_legacy"]
        screen._add_table()
        self.assertTrue(screen._dirty)

        with mock.patch("src.gui_schema_project.messagebox.askyesnocancel", return_value=None), mock.patch.object(
            screen.app, "go_home"
        ) as go_home:
            screen._on_back_requested()
            go_home.assert_not_called()

    def test_legacy_dirty_guard_allows_back_on_discard(self):
        screen = self.app.screens["schema_project_legacy"]
        screen._add_table()
        self.assertTrue(screen._dirty)

        with mock.patch("src.gui_schema_project.messagebox.askyesnocancel", return_value=False), mock.patch.object(
            screen.app, "go_home"
        ) as go_home:
            screen._on_back_requested()
            go_home.assert_called_once()

    def test_legacy_inline_validation_jump_selects_target_column(self):
        screen = self.app.screens["schema_project_legacy"]
        screen._add_table()
        table = screen.project.tables[0].table_name
        column = f"{table}_id"
        issue = ValidationIssue(
            severity="error",
            scope="column",
            table=table,
            column=column,
            message="Test validation issue",
        )
        entry = InlineValidationEntry(
            severity="error",
            location=f"Table '{table}', column '{column}'",
            message="Test validation issue",
            jump_payload=issue,
        )

        screen._jump_to_validation_issue(entry)
        selected = screen.columns_tree.selection()
        self.assertEqual(len(selected), 1)
        values = screen.columns_tree.item(selected[0], "values")
        self.assertEqual(str(values[0]), column)


if __name__ == "__main__":
    unittest.main()
