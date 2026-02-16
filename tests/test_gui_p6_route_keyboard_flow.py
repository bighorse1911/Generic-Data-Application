import tkinter as tk
import unittest

from src.config import AppConfig
from src.gui_home import App


class TestP6RouteKeyboardFlow(unittest.TestCase):
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

    def test_route_scoped_shortcut_activation_switches_between_screens(self) -> None:
        self.app.show_screen("schema_project")
        schema = self.app.screens["schema_project"]
        self.assertTrue(schema.shortcut_manager.is_active)

        self.app.show_screen("home")
        self.assertFalse(schema.shortcut_manager.is_active)

        self.app.show_screen("schema_project_legacy")
        legacy = self.app.screens["schema_project_legacy"]
        self.assertTrue(legacy.shortcut_manager.is_active)
        self.assertGreater(len(legacy.focus_controller.anchor_ids()), 0)

        self.app.show_screen("execution_orchestrator")
        orchestrator = self.app.screens["execution_orchestrator"]
        self.assertFalse(legacy.shortcut_manager.is_active)
        self.assertTrue(orchestrator.shortcut_manager.is_active)
        self.assertGreater(len(orchestrator.focus_controller.anchor_ids()), 0)

        self.app.show_screen("run_center_v2")
        run_center = self.app.screens["run_center_v2"]
        self.assertFalse(orchestrator.shortcut_manager.is_active)
        self.assertTrue(run_center.shortcut_manager.is_active)
        self.assertGreater(len(run_center.focus_controller.anchor_ids()), 0)

    def test_alias_route_does_not_deactivate_shared_schema_screen(self) -> None:
        self.app.show_screen("schema_project")
        schema = self.app.screens["schema_project"]
        self.assertTrue(schema.shortcut_manager.is_active)

        self.app.show_screen("schema_project_kit")
        self.assertTrue(schema.shortcut_manager.is_active)


if __name__ == "__main__":
    unittest.main()
