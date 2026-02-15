import tkinter as tk
import unittest

from src.config import AppConfig
from src.gui_home import App
from src.gui_tools.run_workflow_view import RunWorkflowSurface


class TestGUIRunWorkflowConvergence(unittest.TestCase):
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

    def test_three_run_routes_share_surface_pattern(self):
        for route in ("run_center_v2", "performance_workbench", "execution_orchestrator"):
            screen = self.app.screens[route]
            self.assertTrue(hasattr(screen, "surface"))
            self.assertIsInstance(screen.surface, RunWorkflowSurface)
            self.assertTrue(hasattr(screen, "lifecycle"))
            self.assertTrue(hasattr(screen, "ui_dispatch"))

    def test_route_smoke_and_required_widget_contracts(self):
        self.app.show_screen("run_center_v2")
        self.app.show_screen("performance_workbench")
        self.app.show_screen("execution_orchestrator")

        perf = self.app.screens["performance_workbench"]
        self.assertIsNotNone(perf.diagnostics_tree)
        self.assertIsNotNone(perf.chunk_plan_tree)
        self.assertIsNotNone(perf.run_benchmark_btn)
        self.assertIsNotNone(perf.run_generate_btn)
        self.assertIsNotNone(perf.cancel_run_btn)

        orchestrator = self.app.screens["execution_orchestrator"]
        self.assertIsNotNone(orchestrator.partition_tree)
        self.assertIsNotNone(orchestrator.worker_tree)
        self.assertIsNotNone(orchestrator.failures_tree)
        self.assertIsNotNone(orchestrator.start_run_btn)
        self.assertIsNotNone(orchestrator.start_fallback_btn)
        self.assertIsNotNone(orchestrator.cancel_run_btn)

        run_center = self.app.screens["run_center_v2"]
        self.assertIsNotNone(run_center.progress)
        self.assertIsNotNone(run_center.preview_table)
        self.assertIsNotNone(run_center.diagnostics_tree)
        self.assertIsNotNone(run_center.estimate_btn)
        self.assertIsNotNone(run_center.run_benchmark_btn)
        self.assertIsNotNone(run_center.start_run_btn)
        self.assertIsNotNone(run_center.cancel_run_btn)


if __name__ == "__main__":
    unittest.main()
