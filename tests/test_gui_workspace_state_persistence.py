import os
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

from src.config import AppConfig
from src.gui_home import App
from src.gui_route_policy import SCHEMA_V2_ROUTE

# Coverage handoff:
# - No test removals in this module.
# - Quality hardening only: headless Tk environments now skip cleanly.


class TestGuiWorkspaceStatePersistence(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._state_path = Path(self._tmp_dir.name) / "workspace_state.json"
        self._old_workspace_env = os.environ.get("GDA_WORKSPACE_STATE_PATH")
        os.environ["GDA_WORKSPACE_STATE_PATH"] = str(self._state_path)
        self._roots: list[tk.Tk] = []

    def tearDown(self) -> None:
        for root in self._roots:
            if root.winfo_exists():
                root.destroy()
        if self._old_workspace_env is None:
            os.environ.pop("GDA_WORKSPACE_STATE_PATH", None)
        else:
            os.environ["GDA_WORKSPACE_STATE_PATH"] = self._old_workspace_env
        self._tmp_dir.cleanup()

    def _build_schema_screen(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk GUI not available in this environment: {exc}")
        self._roots.append(root)
        root.withdraw()
        app = App(root, AppConfig())
        return app.screens[SCHEMA_V2_ROUTE]

    def test_schema_v2_workspace_state_restores_across_app_restart(self) -> None:
        first = self._build_schema_screen()
        first.main_tabs.select(first.generate_tab)
        first.project_panel.collapse()
        first.columns_panel.collapse()
        first.relationships_panel.expand()
        first.generate_panel.collapse()
        first.preview_page_size_var.set("500")
        first._on_preview_page_size_changed()
        first._preview_column_preferences = {
            "orders": ["order_id", "amount"],
            "customers": ["customer_id", "name"],
        }
        first._persist_workspace_state()
        self.assertTrue(self._state_path.exists())

        second = self._build_schema_screen()
        selected_tab = second.main_tabs.index(second.main_tabs.select())
        self.assertEqual(selected_tab, second.main_tabs.index(second.generate_tab))
        self.assertTrue(second.project_panel.is_collapsed)
        self.assertTrue(second.columns_panel.is_collapsed)
        self.assertFalse(second.relationships_panel.is_collapsed)
        self.assertTrue(second.generate_panel.is_collapsed)
        self.assertEqual(second.preview_page_size_var.get(), "500")
        self.assertEqual(
            second._preview_column_preferences.get("orders"),
            ["order_id", "amount"],
        )
        self.assertEqual(
            second._preview_column_preferences.get("customers"),
            ["customer_id", "name"],
        )


if __name__ == "__main__":
    unittest.main()
