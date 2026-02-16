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

    def _run_routes(self) -> tuple[str, ...]:
        return (
            "run_center_v2",
            "performance_workbench",
            "execution_orchestrator",
            "performance_workbench_v2",
            "execution_orchestrator_v2",
        )

    def test_three_run_routes_share_surface_pattern(self):
        for route in self._run_routes():
            screen = self.app.screens[route]
            self.assertTrue(hasattr(screen, "surface"))
            self.assertIsInstance(screen.surface, RunWorkflowSurface)
            self.assertTrue(hasattr(screen, "lifecycle"))
            self.assertTrue(hasattr(screen, "ui_dispatch"))
            self.assertTrue(hasattr(screen, "shortcut_manager"))
            self.assertTrue(hasattr(screen, "focus_controller"))
            for api_name in (
                "set_diagnostics_rows",
                "set_plan_rows",
                "set_worker_rows",
                "set_failures_rows",
                "set_history_rows",
            ):
                self.assertTrue(hasattr(screen.surface, api_name))

    def test_route_smoke_and_required_widget_contracts(self):
        self.app.show_screen("run_center_v2")
        self.app.show_screen("performance_workbench")
        self.app.show_screen("execution_orchestrator")
        self.app.show_screen("performance_workbench_v2")
        self.app.show_screen("execution_orchestrator_v2")

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

        perf_v2 = self.app.screens["performance_workbench_v2"]
        self.assertIsNotNone(perf_v2.diagnostics_tree)
        self.assertIsNotNone(perf_v2.chunk_plan_tree)
        self.assertIsNotNone(perf_v2.run_benchmark_btn)
        self.assertIsNotNone(perf_v2.run_generate_btn)
        self.assertIsNotNone(perf_v2.cancel_run_btn)

        orchestrator_v2 = self.app.screens["execution_orchestrator_v2"]
        self.assertIsNotNone(orchestrator_v2.partition_tree)
        self.assertIsNotNone(orchestrator_v2.worker_tree)
        self.assertIsNotNone(orchestrator_v2.failures_tree)
        self.assertIsNotNone(orchestrator_v2.start_run_btn)
        self.assertIsNotNone(orchestrator_v2.start_fallback_btn)
        self.assertIsNotNone(orchestrator_v2.cancel_run_btn)

        run_center = self.app.screens["run_center_v2"]
        self.assertIsNotNone(run_center.progress)
        self.assertIsNotNone(run_center.preview_table)
        self.assertIsNotNone(run_center.diagnostics_tree)
        self.assertIsNotNone(run_center.estimate_btn)
        self.assertIsNotNone(run_center.run_benchmark_btn)
        self.assertIsNotNone(run_center.start_run_btn)
        self.assertIsNotNone(run_center.cancel_run_btn)

    def test_run_surface_tables_use_large_data_mode(self):
        for route in self._run_routes():
            surface = self.app.screens[route].surface
            for adapter in (
                surface.diagnostics_table,
                surface.plan_table,
                surface.worker_table,
                surface.failures_table,
                surface.history_table,
            ):
                if adapter is None:
                    continue
                self.assertTrue(adapter.view._large_data_enabled)

    def test_surface_clear_tree_uses_adapter_clear(self):
        perf = self.app.screens["performance_workbench"]
        perf.surface.set_diagnostics_rows([("t", "1", "1.0", "1.0", "1.0", "low", "ok")])
        self.root.update_idletasks()
        self.root.update()
        self.assertEqual(len(perf.diagnostics_tree.get_children()), 1)
        perf.surface.clear_tree(perf.diagnostics_tree)
        self.root.update_idletasks()
        self.root.update()
        self.assertEqual(len(perf.diagnostics_tree.get_children()), 0)

    def test_run_center_shortcuts_toggle_with_route_lifecycle(self):
        run_center = self.app.screens["run_center_v2"]
        self.assertFalse(run_center.shortcut_manager.is_active)

        self.app.show_screen("run_center_v2")
        self.assertEqual(self.app.current_screen_name, "run_center_v2")
        self.assertTrue(run_center.shortcut_manager.is_active)

        self.app.show_screen("home_v2")
        self.assertEqual(self.app.current_screen_name, "home_v2")
        self.assertFalse(run_center.shortcut_manager.is_active)

        self.app.show_screen("run_center_v2")
        self.assertEqual(self.app.current_screen_name, "run_center_v2")
        self.assertTrue(run_center.shortcut_manager.is_active)


if __name__ == "__main__":
    unittest.main()
