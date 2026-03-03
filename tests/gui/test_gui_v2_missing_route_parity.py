import tkinter as tk
import unittest

from src.config import AppConfig
from src.gui_home import App
from src.gui_route_policy import ORCHESTRATOR_V2_ROUTE
from src.gui_route_policy import PERFORMANCE_V2_ROUTE
from src.gui_route_policy import SCHEMA_V2_ROUTE

# Coverage handoff (de-duplication):
# - Removed route registration/type and general navigability tests from this module.
# - Canonical ownership remains in:
#   tests/test_invariants.py::test_gui_navigation_contract_v2_only.


class TestGuiV2MissingRouteParity(unittest.TestCase):
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

    def test_home_v2_includes_new_route_cards(self) -> None:
        home_v2 = self.app.screens["home_v2"]
        labels = []

        def _collect_text(widget: tk.Widget) -> None:
            try:
                text = str(widget.cget("text"))
            except Exception:  # noqa: BLE001
                text = ""
            if text:
                labels.append(text)
            for child in widget.winfo_children():
                _collect_text(child)

        _collect_text(home_v2)
        all_text = "\n".join(labels)
        self.assertIn("Schema Project v2", all_text)
        self.assertIn("Performance Workbench v2", all_text)
        self.assertIn("Execution Orchestrator v2", all_text)

    def test_new_v2_routes_expose_core_lifecycle_contracts(self) -> None:
        schema_v2 = self.app.screens[SCHEMA_V2_ROUTE]
        self.assertTrue(hasattr(schema_v2, "shortcut_manager"))
        self.assertTrue(hasattr(schema_v2, "focus_controller"))
        self.assertTrue(hasattr(schema_v2, "preview_table"))

        perf_v2 = self.app.screens[PERFORMANCE_V2_ROUTE]
        self.assertTrue(hasattr(perf_v2, "shell"))
        self.assertTrue(hasattr(perf_v2, "surface"))
        self.assertTrue(hasattr(perf_v2, "lifecycle"))
        self.assertTrue(hasattr(perf_v2, "shortcut_manager"))
        self.assertIsNotNone(perf_v2.diagnostics_tree)
        self.assertIsNotNone(perf_v2.chunk_plan_tree)
        self.assertIsNotNone(perf_v2.cancel_run_btn)

        orchestrator_v2 = self.app.screens[ORCHESTRATOR_V2_ROUTE]
        self.assertTrue(hasattr(orchestrator_v2, "shell"))
        self.assertTrue(hasattr(orchestrator_v2, "surface"))
        self.assertTrue(hasattr(orchestrator_v2, "lifecycle"))
        self.assertTrue(hasattr(orchestrator_v2, "shortcut_manager"))
        self.assertIsNotNone(orchestrator_v2.partition_tree)
        self.assertIsNotNone(orchestrator_v2.worker_tree)
        self.assertIsNotNone(orchestrator_v2.failures_tree)
        self.assertIsNotNone(orchestrator_v2.cancel_run_btn)


if __name__ == "__main__":
    unittest.main()


