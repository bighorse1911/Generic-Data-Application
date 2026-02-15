import tkinter as tk
import unittest

from src.config import AppConfig
from src.gui_home import App


EXPECTED_TITLES = {
    "schema_project": ("Schema project error", "Schema project warning"),
    "schema_project_kit": ("Schema project error", "Schema project warning"),
    "schema_project_legacy": ("Schema project legacy error", "Schema project legacy warning"),
    "erd_designer": ("ERD designer error", "ERD designer warning"),
    "erd_designer_v2": ("ERD designer error", "ERD designer warning"),
    "location_selector": ("Location selector error", "Location selector warning"),
    "location_selector_v2": ("Location selector error", "Location selector warning"),
    "performance_workbench": ("Performance workbench error", "Performance workbench warning"),
    "execution_orchestrator": ("Execution orchestrator error", "Execution orchestrator warning"),
    "run_center_v2": ("Run Center v2 error", "Run Center v2 warning"),
}

READ_ONLY_ROUTES = (
    "home",
    "home_v2",
    "schema_studio_v2",
    "generation_behaviors_guide",
    "generation_behaviors_guide_v2",
    "erd_designer_v2_bridge",
    "location_selector_v2_bridge",
    "generation_behaviors_guide_v2_bridge",
)


class TestGuiErrorSurfaceConsistency(unittest.TestCase):
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

    def test_interactive_routes_have_standardized_error_and_warning_titles(self) -> None:
        for route, (error_title, warning_title) in EXPECTED_TITLES.items():
            with self.subTest(route=route):
                screen = self.app.screens[route]
                surface = getattr(screen, "error_surface", None)
                if surface is None and hasattr(screen, "tool"):
                    surface = getattr(screen.tool, "error_surface", None)
                self.assertIsNotNone(surface)
                self.assertEqual(surface.dialog_title, error_title)
                self.assertEqual(surface.warning_title, warning_title)

    def test_read_only_routes_remain_outside_error_surface_runtime_scope(self) -> None:
        for route in READ_ONLY_ROUTES:
            with self.subTest(route=route):
                screen = self.app.screens[route]
                self.assertFalse(hasattr(screen, "error_surface"))


if __name__ == "__main__":
    unittest.main()
