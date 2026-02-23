from types import SimpleNamespace
import tempfile
import tkinter as tk
import unittest
from unittest import mock

from src.config import AppConfig
from src.gui_home import App
from src.gui_route_policy import PERFORMANCE_V2_ROUTE
from src.performance_scaling import ChunkPlanEntry

# Coverage handoff (de-duplication):
# - Removed duplicate route-alias subtests that exercised the same route key twice.
# - Route registration and v2 navigation ownership remains in:
#   tests/test_invariants.py::test_gui_navigation_contract_v2_only.


class TestGuiPerformanceWorkbenchV2Parity(unittest.TestCase):
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

    def test_estimate_and_plan_paths_use_bulk_surface_setters(self) -> None:
        estimate_payload = SimpleNamespace(
            estimates=[
                SimpleNamespace(
                    table_name="orders",
                    estimated_rows=10,
                    estimated_memory_mb=1.0,
                    estimated_write_mb=1.0,
                    estimated_seconds=1.0,
                    risk_level="low",
                    recommendation="ok",
                )
            ],
            summary=SimpleNamespace(
                total_rows=10,
                total_memory_mb=1.0,
                total_write_mb=1.0,
                total_seconds=1.0,
                highest_risk="low",
            ),
        )
        plan_payload = [
            ChunkPlanEntry(
                table_name="orders",
                stage=0,
                chunk_index=1,
                start_row=1,
                end_row=10,
                rows_in_chunk=10,
            )
        ]

        screen = self.app.screens[PERFORMANCE_V2_ROUTE]
        screen.project = object()

        with mock.patch.object(screen, "_ensure_project", return_value=True), mock.patch(
            "src.gui_performance_workbench_base.run_shared_estimate",
            return_value=estimate_payload,
        ), mock.patch.object(screen.surface, "set_diagnostics_rows") as set_diagnostics:
            screen._estimate_workload()
            set_diagnostics.assert_called_once()

        with mock.patch.object(screen, "_ensure_project", return_value=True), mock.patch(
            "src.gui_performance_workbench_base.run_build_chunk_plan",
            return_value=plan_payload,
        ), mock.patch.object(screen.surface, "set_plan_rows") as set_plan:
            screen._build_chunk_plan()
            set_plan.assert_called_once()

    def test_benchmark_and_generate_paths_use_lifecycle_callbacks(self) -> None:
        benchmark_result = SimpleNamespace(
            selected_tables=["orders"],
            estimates=[
                SimpleNamespace(
                    table_name="orders",
                    estimated_rows=10,
                    estimated_memory_mb=1.0,
                    estimated_write_mb=1.0,
                    estimated_seconds=1.0,
                    risk_level="low",
                    recommendation="ok",
                )
            ],
            chunk_plan=[
                SimpleNamespace(
                    table_name="orders",
                    stage=0,
                    chunk_index=1,
                    start_row=1,
                    end_row=10,
                    rows_in_chunk=10,
                )
            ],
            chunk_summary=SimpleNamespace(total_chunks=1, total_rows=10),
            estimate_summary=SimpleNamespace(highest_risk="low"),
        )
        generate_result = SimpleNamespace(
            selected_tables=["orders"],
            total_rows=10,
            csv_paths={},
            sqlite_counts={},
        )

        def _run_async_benchmark(**kwargs):
            kwargs["on_done"](benchmark_result)
            return True

        def _run_async_generate(**kwargs):
            kwargs["on_done"](generate_result)
            return True

        screen = self.app.screens[PERFORMANCE_V2_ROUTE]
        screen.project = object()

        with mock.patch.object(screen, "_ensure_project", return_value=True), mock.patch.object(
            screen.lifecycle,
            "run_async",
            side_effect=_run_async_benchmark,
        ), mock.patch.object(screen.surface, "set_diagnostics_rows") as set_diag, mock.patch.object(
            screen.surface,
            "set_plan_rows",
        ) as set_plan:
            screen._start_run_benchmark()
            set_diag.assert_called_once()
            set_plan.assert_called_once()

        with mock.patch.object(screen, "_ensure_project", return_value=True), mock.patch(
            "src.gui_performance_workbench_base.build_profile_from_model",
            return_value=SimpleNamespace(output_mode="preview"),
        ), mock.patch.object(
            screen.lifecycle,
            "run_async",
            side_effect=_run_async_generate,
        ):
            screen._start_generate_with_strategy()
            self.assertFalse(screen.lifecycle.state.is_running)
            self.assertIn("Generation complete", screen.surface.status_var.get())

    def test_cancel_and_profile_save_load_paths(self) -> None:
        screen = self.app.screens[PERFORMANCE_V2_ROUTE]
        screen.lifecycle.set_running(True, "Running")
        screen._cancel_run()
        self.assertTrue(screen.lifecycle.state.cancel_requested)
        screen.lifecycle.set_running(False, "Idle")

        with tempfile.TemporaryDirectory() as tmp_dir:
            profile_path = f"{tmp_dir}/profile.json"
            with mock.patch("src.gui_performance_workbench_base.build_profile_from_model", return_value=SimpleNamespace(output_mode="preview")), mock.patch(
                "src.gui_performance_workbench_base.performance_profile_payload",
                return_value={"output_mode": "preview"},
            ), mock.patch(
                "src.gui_performance_workbench_base.filedialog.asksaveasfilename",
                return_value=profile_path,
            ):
                screen._save_profile()
            self.assertTrue(screen.surface.status_var.get().startswith("Saved performance profile"))

            with mock.patch("src.gui_performance_workbench_base.filedialog.askopenfilename", return_value=profile_path), mock.patch(
                "src.gui_performance_workbench_base.apply_performance_profile_payload",
            ), mock.patch(
                "src.gui_performance_workbench_base.build_profile_from_model",
                return_value=SimpleNamespace(output_mode="preview"),
            ):
                screen._load_profile()
            self.assertTrue(screen.surface.status_var.get().startswith("Loaded performance profile"))


if __name__ == "__main__":
    unittest.main()


