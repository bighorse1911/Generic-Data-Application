import tkinter as tk
import unittest

from src.config import AppConfig
from src.gui_home import App
from src.gui_route_policy import RUN_CENTER_V2_ROUTE
from src.gui_route_policy import SCHEMA_V2_ROUTE


class TestGuiCommandPalette(unittest.TestCase):
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

    def _pump(self, cycles: int = 4) -> None:
        for _ in range(cycles):
            self.root.update_idletasks()
            self.root.update()

    def test_ctrl_k_opens_palette_and_exposes_route_actions(self) -> None:
        self.assertFalse(self.app.command_palette.is_open)
        self.assertIn("<Control-k>", self.app._global_shortcut_bindings)
        self.app._on_open_command_palette_shortcut()
        self._pump()
        self.assertTrue(self.app.command_palette.is_open)
        self.assertIn("route:home_v2", self.app.command_palette.result_action_ids)
        self.assertIn("route:schema_project_v2", self.app.command_palette.result_action_ids)
        self.app.command_palette.close()
        self._pump()

    def test_registry_includes_schema_high_frequency_actions(self) -> None:
        self.app.show_screen(SCHEMA_V2_ROUTE)
        registry = self.app._build_command_palette_registry()
        action_ids = {action.action_id for action in registry.actions()}

        self.assertIn("schema_project_v2:load", action_ids)
        self.assertIn("schema_project_v2:save", action_ids)
        self.assertIn("schema_project_v2:validate", action_ids)
        self.assertIn("schema_project_v2:generate", action_ids)

    def test_dispatch_route_jump_action_changes_current_route(self) -> None:
        self.assertEqual(self.app.current_screen_name, "home_v2")
        dispatched = self.app.command_palette.dispatch_action(f"route:{RUN_CENTER_V2_ROUTE}")
        self._pump()
        self.assertTrue(dispatched)
        self.assertEqual(self.app.current_screen_name, RUN_CENTER_V2_ROUTE)

    def test_palette_shortcut_coexists_with_route_shortcuts(self) -> None:
        self.app.show_screen(SCHEMA_V2_ROUTE)
        schema = self.app.screens[SCHEMA_V2_ROUTE]
        self.assertTrue(schema.shortcut_manager.is_active)
        bindings_before = len(schema.shortcut_manager._bound_ids.get("<Control-f>", []))
        self.assertGreater(bindings_before, 0)

        self.app._on_open_command_palette_shortcut()
        self._pump()
        self.assertTrue(self.app.command_palette.is_open)
        self.app.command_palette.close()
        self._pump()

        self.assertTrue(schema.shortcut_manager.is_active)
        bindings_after = len(schema.shortcut_manager._bound_ids.get("<Control-f>", []))
        self.assertEqual(bindings_after, bindings_before)


if __name__ == "__main__":
    unittest.main()
