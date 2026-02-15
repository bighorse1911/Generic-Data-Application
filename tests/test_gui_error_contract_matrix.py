import tkinter as tk
import unittest

from src.config import AppConfig
from src.gui_home import App
from src.gui_kit.error_surface import is_actionable_message


class TestGuiErrorContractMatrix(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:  # pragma: no cover - depends on CI display support
            self.skipTest(f"Tk GUI not available in this environment: {exc}")
            return
        self.root.withdraw()
        self.app = App(self.root, AppConfig())

    def tearDown(self) -> None:
        if hasattr(self, "root") and self.root.winfo_exists():
            self.root.destroy()

    @staticmethod
    def _capture_surface(screen) -> tuple[object, list[tuple[str, str]], list[tuple[str, str]]]:
        target = getattr(screen, "error_surface", None)
        if target is None and hasattr(screen, "tool"):
            target = getattr(screen.tool, "error_surface", None)
        assert target is not None
        dialogs: list[tuple[str, str]] = []
        warnings: list[tuple[str, str]] = []
        target.show_dialog = lambda title, message: dialogs.append((title, message))
        target.show_warning = lambda title, message: warnings.append((title, message))
        return target, dialogs, warnings

    def test_schema_primary_route_uses_actionable_error_and_warning_contract(self) -> None:
        screen = self.app.screens["schema_project"]
        _, dialogs, warnings = self._capture_surface(screen)

        screen.seed_var.set("invalid_seed")
        screen._run_validation()
        self.assertEqual(len(dialogs), 1)
        title, message = dialogs[0]
        self.assertEqual(title, "Schema project error")
        self.assertTrue(is_actionable_message(message))

        dialogs.clear()
        screen.seed_var.set(str(AppConfig().seed))
        screen._run_validation()
        screen.generated_rows = {}
        screen._on_export_csv()
        self.assertEqual(len(warnings), 1)
        warning_title, warning_message = warnings[0]
        self.assertEqual(warning_title, "Schema project warning")
        self.assertTrue(is_actionable_message(warning_message))

    def test_schema_legacy_route_uses_legacy_titles(self) -> None:
        screen = self.app.screens["schema_project_legacy"]
        _, dialogs, _warnings = self._capture_surface(screen)

        screen.seed_var.set("legacy_seed_invalid")
        screen._run_validation()
        self.assertEqual(len(dialogs), 1)
        title, message = dialogs[0]
        self.assertEqual(title, "Schema project legacy error")
        self.assertTrue(is_actionable_message(message))

    def test_tool_routes_erd_and_location_emit_actionable_precondition_errors(self) -> None:
        erd_screen = self.app.screens["erd_designer"]
        _, dialogs, _warnings = self._capture_surface(erd_screen)
        erd_screen.project = None
        erd_screen._export_schema_json()
        self.assertEqual(len(dialogs), 1)
        erd_title, erd_message = dialogs[0]
        self.assertEqual(erd_title, "ERD designer error")
        self.assertTrue(is_actionable_message(erd_message))

        location_screen = self.app.screens["location_selector"]
        _, loc_dialogs, _loc_warnings = self._capture_surface(location_screen)
        location_screen._latest_points = []
        location_screen._save_points_csv()
        self.assertEqual(len(loc_dialogs), 1)
        loc_title, loc_message = loc_dialogs[0]
        self.assertEqual(loc_title, "Location selector error")
        self.assertTrue(is_actionable_message(loc_message))

    def test_native_v2_tool_routes_share_actionable_error_contract(self) -> None:
        erd_screen = self.app.screens["erd_designer_v2"]
        _, dialogs, _warnings = self._capture_surface(erd_screen)
        erd_screen.tool.project = None
        erd_screen.tool._export_schema_json()
        self.assertEqual(len(dialogs), 1)
        erd_title, erd_message = dialogs[0]
        self.assertEqual(erd_title, "ERD designer error")
        self.assertTrue(is_actionable_message(erd_message))

        location_screen = self.app.screens["location_selector_v2"]
        _, loc_dialogs, _loc_warnings = self._capture_surface(location_screen)
        location_screen.tool._latest_points = []
        location_screen.tool._save_points_csv()
        self.assertEqual(len(loc_dialogs), 1)
        loc_title, loc_message = loc_dialogs[0]
        self.assertEqual(loc_title, "Location selector error")
        self.assertTrue(is_actionable_message(loc_message))

    def test_run_routes_emit_actionable_schema_path_errors(self) -> None:
        expectations = {
            "performance_workbench": "Performance workbench error",
            "execution_orchestrator": "Execution orchestrator error",
            "run_center_v2": "Run Center v2 error",
        }
        for route, expected_title in expectations.items():
            with self.subTest(route=route):
                screen = self.app.screens[route]
                _, dialogs, _warnings = self._capture_surface(screen)
                screen.surface.schema_path_var.set("")
                ok = screen._load_schema()
                self.assertFalse(ok)
                self.assertEqual(len(dialogs), 1)
                title, message = dialogs[0]
                self.assertEqual(title, expected_title)
                self.assertTrue(is_actionable_message(message))


if __name__ == "__main__":
    unittest.main()
