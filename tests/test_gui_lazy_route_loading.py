import tkinter as tk
import unittest
from unittest import mock

from src.config import AppConfig
from src.gui_home import App
from src.gui_route_policy import HOME_V2_ROUTE
from src.gui_route_policy import ORCHESTRATOR_V2_ROUTE
from src.gui_route_policy import PERFORMANCE_V2_ROUTE
from src.gui_route_policy import RUN_CENTER_V2_ROUTE
from src.gui_route_policy import SCHEMA_STUDIO_V2_ROUTE
from src.gui_route_policy import SCHEMA_V2_ROUTE


class TestGuiLazyRouteLoading(unittest.TestCase):
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

    def _drain_idle(self, cycles: int = 4) -> None:
        for _ in range(cycles):
            self.root.update_idletasks()
            self.root.update()

    def test_only_home_route_is_loaded_immediately(self) -> None:
        self.assertIsNotNone(self.app.screens.get(HOME_V2_ROUTE))
        self.assertIsNone(self.app.screens.get(SCHEMA_STUDIO_V2_ROUTE))
        self.assertIsNone(self.app.screens.get(SCHEMA_V2_ROUTE))
        self.assertIsNone(self.app.screens.get(RUN_CENTER_V2_ROUTE))

    def test_index_access_lazily_instantiates_requested_route(self) -> None:
        self.assertIsNone(self.app.screens.get(SCHEMA_V2_ROUTE))
        screen = self.app.screens[SCHEMA_V2_ROUTE]
        self.assertIsNotNone(screen)
        self.assertIsNotNone(self.app.screens.get(SCHEMA_V2_ROUTE))

    def test_home_idle_prefetch_loads_likely_next_routes_only(self) -> None:
        self.assertIsNone(self.app.screens.get(SCHEMA_STUDIO_V2_ROUTE))
        self.assertIsNone(self.app.screens.get(RUN_CENTER_V2_ROUTE))
        self.assertIsNone(self.app.screens.get(ORCHESTRATOR_V2_ROUTE))

        self._drain_idle()

        self.assertIsNotNone(self.app.screens.get(SCHEMA_STUDIO_V2_ROUTE))
        self.assertIsNotNone(self.app.screens.get(RUN_CENTER_V2_ROUTE))
        self.assertIsNone(self.app.screens.get(ORCHESTRATOR_V2_ROUTE))

    def test_home_remains_topmost_when_idle_prefetch_builds_other_routes(self) -> None:
        home_screen = self.app.screens[HOME_V2_ROUTE]
        with mock.patch.object(home_screen, "tkraise", wraps=home_screen.tkraise) as home_raise:
            self._drain_idle()
        self.assertGreaterEqual(
            home_raise.call_count,
            1,
            "Idle prefetch must keep the active home route visible after materializing background routes. "
            "Fix: re-raise current screen after prefetch frame creation.",
        )

    def test_run_center_idle_prefetch_loads_performance_and_orchestrator(self) -> None:
        self.app.show_screen(RUN_CENTER_V2_ROUTE)
        self.assertIsNone(self.app.screens.get(PERFORMANCE_V2_ROUTE))
        self.assertIsNone(self.app.screens.get(ORCHESTRATOR_V2_ROUTE))

        self._drain_idle()

        self.assertIsNotNone(self.app.screens.get(PERFORMANCE_V2_ROUTE))
        self.assertIsNotNone(self.app.screens.get(ORCHESTRATOR_V2_ROUTE))


if __name__ == "__main__":
    unittest.main()
