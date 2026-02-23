import time
import tkinter as tk
import unittest
from unittest import mock

from tkinter import ttk

from src.config import AppConfig
from src.gui_home import App


_SIMULATED_SCREEN_INIT_SECONDS = 0.015


class _DelayedScreen(ttk.Frame):
    def __init__(self, parent: tk.Widget, *_args, **_kwargs) -> None:
        time.sleep(_SIMULATED_SCREEN_INIT_SECONDS)
        super().__init__(parent)


def _patch_screen_constructors():
    return mock.patch.multiple(
        "src.gui_home",
        HomeV2Screen=_DelayedScreen,
        SchemaStudioV2Screen=_DelayedScreen,
        SchemaProjectV2Screen=_DelayedScreen,
        RunCenterV2Screen=_DelayedScreen,
        PerformanceWorkbenchV2Screen=_DelayedScreen,
        ExecutionOrchestratorV2Screen=_DelayedScreen,
        ERDDesignerV2Screen=_DelayedScreen,
        LocationSelectorV2Screen=_DelayedScreen,
        GenerationBehaviorsGuideV2Screen=_DelayedScreen,
    )


class TestGuiStartupTiming(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk GUI not available in this environment: {exc}")
            return
        self.root.withdraw()

    def tearDown(self) -> None:
        if hasattr(self, "root") and self.root.winfo_exists():
            self.root.destroy()

    def test_lazy_startup_is_faster_than_full_route_materialization(self) -> None:
        with _patch_screen_constructors():
            startup_begin = time.perf_counter()
            app = App(self.root, AppConfig())
            startup_elapsed = time.perf_counter() - startup_begin

            full_materialization_begin = time.perf_counter()
            for route in sorted(app.screens.keys()):
                _ = app.screens[route]
            full_materialization_elapsed = time.perf_counter() - full_materialization_begin

        self.assertLess(
            startup_elapsed,
            full_materialization_elapsed,
            "Startup timing harness expected lazy startup to be faster than full route materialization. "
            "Fix: keep screen construction lazy at app startup.",
        )
        self.assertGreater(
            full_materialization_elapsed - startup_elapsed,
            _SIMULATED_SCREEN_INIT_SECONDS * 4,
            "Startup timing harness expected a material lazy-startup advantage under simulated heavy route init. "
            "Fix: ensure non-home routes are not built during initial app startup.",
        )


if __name__ == "__main__":
    unittest.main()
