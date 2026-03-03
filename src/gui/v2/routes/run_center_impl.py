from __future__ import annotations

import json
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from src.config import AppConfig
from src.gui_route_policy import ORCHESTRATOR_V2_ROUTE
from src.gui_route_policy import PERFORMANCE_V2_ROUTE
from src.gui_kit.accessibility import FocusController
from src.gui_kit.error_surface import ErrorSurface
from src.gui_kit.error_surface import show_error_dialog
from src.gui_kit.error_surface import show_warning_dialog
from src.gui_kit.feedback import ToastCenter
from src.gui_kit.run_commands import apply_run_center_payload
from src.gui_kit.run_commands import run_center_payload
from src.gui_kit.run_lifecycle import RunLifecycleController
from src.gui_kit.shortcuts import ShortcutManager
from src.gui_kit.ui_dispatch import UIDispatcher
from src.gui_tools.run_workflow_view import RunWorkflowCapabilities
from src.gui_tools.run_workflow_view import RunWorkflowSurface
from src.gui.v2.routes import run_hooks
from src.gui.v2.routes.errors import _v2_error
from src.gui.v2.routes.shell_impl import V2ShellFrame
from src.gui.v2.routes.theme_shared import V2_BG
from src.gui_v2.viewmodels import RunCenterViewModel
from src.multiprocessing_runtime import MultiprocessEvent
from src.multiprocessing_runtime import MultiprocessRunCancelled
from src.multiprocessing_runtime import MultiprocessRunResult
from src.performance_scaling import BenchmarkResult
from src.performance_scaling import PerformanceRunCancelled
from src.performance_scaling import RuntimeEvent
from src.schema_project_io import load_project_from_json

class RunCenterV2Screen(tk.Frame):
    """Feature-C run workflow screen with diagnostics, planning, and execution integration."""

    def __init__(self, parent: tk.Widget, app: object, _cfg: AppConfig) -> None:
        super().__init__(parent, bg=V2_BG)
        self.app = app
        self.project = None
        self._loaded_schema_path = ""

        self.view_model = RunCenterViewModel()

        self.shell = V2ShellFrame(self, title="Run Center v2", on_back=lambda: self.app.show_screen("home_v2"))
        self.shell.pack(fill="both", expand=True)
        self.shell.add_header_action("Orchestrator v2", lambda: self.app.show_screen(ORCHESTRATOR_V2_ROUTE))
        self.shell.add_header_action("Workbench v2", lambda: self.app.show_screen(PERFORMANCE_V2_ROUTE))
        self.shell.add_header_action("Notifications", self._show_notifications_history)
        self.shell.add_header_action("Shortcuts", self._show_shortcuts_help)
        self.shell.add_header_action("Schema Studio", lambda: self.app.show_screen("schema_studio_v2"))

        self.shell.add_nav_button("config", "Run Config", lambda: self._set_focus("config"))
        self.shell.add_nav_button("diagnostics", "Diagnostics", lambda: self._set_focus("diagnostics"))
        self.shell.add_nav_button("plan", "Plan", lambda: self._set_focus("plan"))
        self.shell.add_nav_button("failures", "Failures", lambda: self._set_focus("failures"))
        self.shell.add_nav_button("history", "History", lambda: self._set_focus("history"))
        self.shell.set_nav_active("config")

        self.surface = RunWorkflowSurface(
            self.shell.workspace,
            model=self.view_model,
            capabilities=RunWorkflowCapabilities(
                estimate=True,
                build_plan=True,
                benchmark=True,
                start_run=True,
                start_fallback=True,
                failures_tab=True,
                history_tab=True,
                show_status_label=False,
            ),
            status_callback=self.shell.set_status,
        )
        self.surface.pack(fill="both", expand=True, padx=10, pady=10)

        self.surface.browse_btn.configure(command=self._browse_schema_path)
        self.surface.load_schema_btn.configure(command=self._load_schema)
        self.surface.estimate_btn.configure(command=self._run_estimate)
        self.surface.build_plan_btn.configure(command=self._run_build_plan)
        self.surface.run_benchmark_btn.configure(command=self._start_benchmark)
        self.surface.start_run_btn.configure(command=self._start_generation)
        self.surface.start_fallback_btn.configure(command=lambda: self._start_generation(fallback_to_single_process=True))
        self.surface.cancel_run_btn.configure(command=self._cancel_run)
        self.surface.save_btn.configure(command=self._save_profile)
        self.surface.load_btn.configure(command=self._load_profile)

        self.progress = self.surface.progress
        self.preview_table = self.surface.preview_table
        self.diagnostics_tree = self.surface.diagnostics_tree
        self.failures_tree = self.surface.failures_tree
        self.history_tree = self.surface.history_tree
        self.estimate_btn = self.surface.estimate_btn
        self.build_plan_btn = self.surface.build_plan_btn
        self.run_benchmark_btn = self.surface.run_benchmark_btn
        self.start_run_btn = self.surface.start_run_btn
        self.start_fallback_btn = self.surface.start_fallback_btn
        self.cancel_run_btn = self.surface.cancel_run_btn
        self.live_phase_var = self.surface.live_phase_var
        self.live_rows_var = self.surface.live_rows_var
        self.live_eta_var = self.surface.live_eta_var

        self.error_surface = ErrorSurface(
            context="Run Center v2",
            dialog_title="Run Center v2 error",
            warning_title="Run Center v2 warning",
            show_dialog=show_error_dialog,
            show_warning=show_warning_dialog,
            set_status=self.shell.set_status,
            set_inline=self.surface.set_inline_error,
        )
        self.ui_dispatch = UIDispatcher.from_widget(self)

        self.lifecycle = RunLifecycleController(
            set_phase=self.live_phase_var.set,
            set_rows=self.live_rows_var.set,
            set_eta=self.live_eta_var.set,
            set_progress=lambda value: self.progress.configure(value=value),
            set_status=self.shell.set_status,
            action_buttons=self.surface.run_action_buttons,
            cancel_button=self.surface.cancel_run_btn,
        )
        self.shortcut_manager = ShortcutManager(self)
        self.focus_controller = FocusController(self)
        self.toast_center = ToastCenter(self)
        self._register_focus_anchors()
        self._register_shortcuts()

        self._set_inspector_for_config()
        self.shell.set_status("Run Center v2 ready.")

    def on_show(self) -> None:
        self.shortcut_manager.activate()
        self.focus_controller.focus_default()

    def on_hide(self) -> None:
        self.shortcut_manager.deactivate()

    def _register_focus_anchors(self) -> None:
        self.focus_controller.add_anchor(
            "schema_path",
            lambda: getattr(self.surface, "schema_entry", None),
            description="Schema path input",
        )
        self.focus_controller.add_anchor(
            "actions",
            lambda: self.start_run_btn,
            description="Run action controls",
        )
        self.focus_controller.add_anchor(
            "diagnostics",
            lambda: self.diagnostics_tree,
            description="Diagnostics table",
        )
        self.focus_controller.add_anchor(
            "plan",
            lambda: self.preview_table,
            description="Partition plan table",
        )
        self.focus_controller.add_anchor(
            "failures",
            lambda: self.failures_tree,
            description="Failures table",
        )
        self.focus_controller.add_anchor(
            "history",
            lambda: self.history_tree,
            description="Run history table",
        )
        self.focus_controller.set_default_anchor("schema_path")

    def _register_shortcuts(self) -> None:
        self.shortcut_manager.register("<F1>", "Open shortcuts help", self._show_shortcuts_help)
        self.shortcut_manager.register("<F6>", "Focus next major section", self._focus_next_anchor)
        self.shortcut_manager.register("<Shift-F6>", "Focus previous major section", self._focus_previous_anchor)
        self.shortcut_manager.register_ctrl_cmd("b", "Browse schema path", self._browse_schema_path)
        self.shortcut_manager.register_ctrl_cmd("l", "Load schema", self._load_schema)
        self.shortcut_manager.register_ctrl_cmd("s", "Save run config", self._save_profile)
        self.shortcut_manager.register_ctrl_cmd("o", "Load run config", self._load_profile)
        self.shortcut_manager.register("<F5>", "Estimate workload", self._run_estimate)
        self.shortcut_manager.register_ctrl_cmd("Return", "Start run", self._start_generation)
        self.shortcut_manager.register("<Escape>", "Cancel active run", self._cancel_if_running)
        self.shortcut_manager.register_help_item("Ctrl/Cmd+C", "Copy selected table rows with headers")
        self.shortcut_manager.register_help_item("Ctrl/Cmd+Shift+C", "Copy selected table rows without headers")
        self.shortcut_manager.register_help_item("Ctrl/Cmd+A", "Select all rows in focused table")
        self.shortcut_manager.register_help_item("PageUp/PageDown", "Move selection by page in focused table")
        self.shortcut_manager.register_help_item("Ctrl/Cmd+Home", "Jump to first row in focused table")
        self.shortcut_manager.register_help_item("Ctrl/Cmd+End", "Jump to last row in focused table")

    def _focus_next_anchor(self) -> None:
        self.focus_controller.focus_next()

    def _focus_previous_anchor(self) -> None:
        self.focus_controller.focus_previous()

    def _cancel_if_running(self) -> None:
        if self.lifecycle.state.is_running:
            self._cancel_run()

    def _show_shortcuts_help(self) -> None:
        self.shortcut_manager.show_help_dialog(title="Run Center v2 Shortcuts")

    def _show_notifications_history(self) -> None:
        if hasattr(self, "toast_center"):
            self.toast_center.show_history_dialog(title="Run Center Notifications")

    def _notify(self, message: str, *, level: str = "info", duration_ms: int | None = None) -> None:
        text = str(message).strip()
        if text == "":
            return
        self.shell.set_status(text)
        if hasattr(self, "toast_center"):
            self.toast_center.notify(text, level=level, duration_ms=duration_ms)

    def _set_inspector_for_config(self) -> None:
        self.shell.set_inspector(
            "Run Center Notes",
            [
                "Run Center v2 is wired to performance + multiprocessing runtimes.",
                "Estimate/plan/benchmark/start preserve canonical validation and deterministic semantics.",
                "Errors preserve location + fix hints.",
            ],
        )

    def _set_focus(self, key: str) -> None:
        self.shell.set_nav_active(key)
        if key in {"diagnostics", "plan", "failures", "history"}:
            self.surface.set_focus(key)
        self.shell.set_status(f"Run Center v2: focus set to {key}.")

    def _sync_viewmodel_from_vars(self) -> RunCenterViewModel:
        return self.surface.sync_model_from_vars()

    def _browse_schema_path(self) -> None:
        path = run_hooks.filedialog.askopenfilename(
            title="Select schema project JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.surface.schema_path_var.set(path)

    def _load_schema(self) -> bool:
        model = self._sync_viewmodel_from_vars()
        if model.schema_path == "":
            self.error_surface.emit(
                location="Schema path",
                issue="path is required",
                hint="choose an existing schema project JSON file",
                mode="mixed",
            )
            return False
        try:
            loaded = load_project_from_json(model.schema_path)
        except (ValueError, OSError) as exc:
            self.error_surface.emit_exception_actionable(
                exc,
                location="Load schema",
                hint="choose a valid schema project JSON file",
                mode="mixed",
            )
            return False
        self.project = loaded
        self._loaded_schema_path = model.schema_path
        self.shell.set_status(f"Loaded schema '{loaded.name}' with {len(loaded.tables)} tables.")
        self.surface.set_inline_error("")
        return True

    def _ensure_project(self) -> bool:
        model = self._sync_viewmodel_from_vars()
        if self.project is None:
            return self._load_schema()
        if model.schema_path == "":
            return True
        if model.schema_path != self._loaded_schema_path:
            return self._load_schema()
        return True

    def _clear_tree(self, tree: ttk.Treeview | None) -> None:
        self.surface.clear_tree(tree)

    def _set_running(self, running: bool, phase: str) -> None:
        self.lifecycle.set_running(running, phase)

    def _cancel_run(self) -> None:
        self.lifecycle.request_cancel("Cancellation requested. Waiting for current step to stop...")

    def _is_cancel_requested(self) -> bool:
        return self.lifecycle.is_cancel_requested()

    def _append_history(self, status: str, mode: str, fallback: bool, rows: int) -> None:
        if self.history_tree is None:
            return
        self.history_tree.insert(
            "",
            0,
            values=(time.strftime("%Y-%m-%d %H:%M:%S"), status, mode, "yes" if fallback else "no", str(rows)),
        )

    def _on_runtime_event(self, event: RuntimeEvent) -> None:
        self.lifecycle.handle_runtime_event(event)

    def _on_multiprocess_event(self, event: MultiprocessEvent) -> None:
        self.lifecycle.handle_multiprocess_event(event)
        if event.kind == "partition_failed" and event.partition_id and self.failures_tree is not None:
            self.failures_tree.insert(
                "",
                "end",
                values=(event.partition_id, event.message, str(event.retry_count), "retry"),
            )

    def _on_run_failed(self, message: str) -> None:
        self.lifecycle.transition_failed(message, phase="Failed")
        self.error_surface.emit_formatted(message, mode="mixed")
        self._append_history("failed", self.surface.execution_mode_var.get(), False, 0)

    def _on_run_cancelled(self, message: str) -> None:
        self.lifecycle.transition_cancelled(message, phase="Cancelled")
        self.live_phase_var.set("Run cancelled.")
        self.live_eta_var.set("ETA: cancelled")
        self._notify("Run cancelled by user request.", level="warn", duration_ms=3200)
        self._append_history("cancelled", self.surface.execution_mode_var.get(), False, 0)

    def _run_estimate(self) -> None:
        if self.lifecycle.state.is_running or not self._ensure_project():
            return
        assert self.project is not None
        model = self._sync_viewmodel_from_vars()
        try:
            diagnostics = run_hooks.run_shared_estimate(self.project, model)
        except ValueError as exc:
            self.error_surface.emit_exception_actionable(
                exc,
                location="Estimate workload",
                hint="review run profile values and retry",
                mode="mixed",
            )
            return
        self.surface.set_diagnostics_rows(
            [
                (
                    estimate.table_name,
                    str(estimate.estimated_rows),
                    f"{estimate.estimated_memory_mb:.3f}",
                    f"{estimate.estimated_write_mb:.3f}",
                    f"{estimate.estimated_seconds:.3f}",
                    estimate.risk_level,
                    estimate.recommendation,
                )
                for estimate in diagnostics.estimates
            ]
        )
        self._notify(
            f"Estimate complete: rows={diagnostics.summary.total_rows}, risk={diagnostics.summary.highest_risk}.",
            level="success",
            duration_ms=3400,
        )
        self._set_focus("diagnostics")

    def _run_build_plan(self) -> None:
        if self.lifecycle.state.is_running or not self._ensure_project():
            return
        assert self.project is not None
        model = self._sync_viewmodel_from_vars()
        try:
            entries = run_hooks.run_shared_build_partition_plan(self.project, model)
        except ValueError as exc:
            self.error_surface.emit_exception_actionable(
                exc,
                location="Build partition plan",
                hint="review execution settings and retry",
                mode="mixed",
            )
            return
        self.surface.set_plan_rows(
            [
                (
                    entry.table_name,
                    entry.partition_id,
                    f"{entry.start_row}-{entry.end_row}",
                    str(entry.stage),
                    str(entry.assigned_worker),
                    entry.status,
                )
                for entry in entries
            ]
        )
        self._notify(
            f"Partition plan ready: partitions={len(entries)}.",
            level="success",
            duration_ms=3400,
        )
        self._set_focus("plan")

    def _start_benchmark(self) -> None:
        if not self._ensure_project():
            return
        assert self.project is not None
        model = self._sync_viewmodel_from_vars()

        def worker() -> BenchmarkResult:
            return run_hooks.run_shared_benchmark(
                self.project,
                model,
                on_event=self.ui_dispatch.marshal(self._on_runtime_event),
                cancel_requested=self._is_cancel_requested,
            )

        def on_done(result: BenchmarkResult) -> None:
            self.lifecycle.transition_complete("Benchmark complete")
            self.surface.set_diagnostics_rows(
                [
                    (
                        estimate.table_name,
                        str(estimate.estimated_rows),
                        f"{estimate.estimated_memory_mb:.3f}",
                        f"{estimate.estimated_write_mb:.3f}",
                        f"{estimate.estimated_seconds:.3f}",
                        estimate.risk_level,
                        estimate.recommendation,
                    )
                    for estimate in result.estimates
                ]
            )
            self.surface.set_plan_rows(
                [
                    (
                        entry.table_name,
                        f"{entry.table_name}|stage={entry.stage}|chunk={entry.chunk_index}",
                        f"{entry.start_row}-{entry.end_row}",
                        str(entry.stage),
                        "-",
                        "planned",
                    )
                    for entry in result.chunk_plan
                ]
            )
            self._notify(
                f"Benchmark complete: chunks={result.chunk_summary.total_chunks}, rows={result.chunk_summary.total_rows}.",
                level="success",
                duration_ms=3600,
            )
            self._append_history("benchmark_complete", self.surface.execution_mode_var.get(), False, result.chunk_summary.total_rows)

        self.lifecycle.run_async(
            after=self.after,
            worker=worker,
            on_done=lambda payload: on_done(payload),
            on_failed=self._on_run_failed,
            on_cancelled=self._on_run_cancelled,
            phase_label="Running benchmark...",
            cancel_exceptions=(PerformanceRunCancelled,),
            dispatcher=self.ui_dispatch,
        )

    def _start_generation(self, fallback_to_single_process: bool = False) -> None:
        if not self._ensure_project():
            return
        assert self.project is not None
        model = self._sync_viewmodel_from_vars()

        try:
            profile = run_hooks.build_profile_from_model(model)
        except ValueError as exc:
            self.error_surface.emit_exception_actionable(
                exc,
                location="Start generation",
                hint="fix invalid run profile values and retry",
                mode="mixed",
            )
            return

        output_mode = profile.output_mode
        output_csv_folder: str | None = None
        output_sqlite_path: str | None = None

        if output_mode in {"csv", "all"}:
            output_csv_folder = run_hooks.filedialog.askdirectory(title="Choose output folder for CSV export")
            if output_csv_folder in {None, ""}:
                self.shell.set_status("Run cancelled (no CSV output folder selected).")
                return
        if output_mode in {"sqlite", "all"}:
            output_sqlite_path = run_hooks.filedialog.asksaveasfilename(
                title="Choose SQLite output path",
                defaultextension=".db",
                filetypes=[("SQLite DB", "*.db"), ("All files", "*.*")],
                initialfile="run_center_v2.db",
            )
            if output_sqlite_path in {None, ""}:
                self.shell.set_status("Run cancelled (no SQLite output path selected).")
                return

        def worker() -> MultiprocessRunResult:
            return run_hooks.run_generation_multiprocess(
                self.project,
                model,
                output_csv_folder=output_csv_folder,
                output_sqlite_path=output_sqlite_path,
                on_event=self.ui_dispatch.marshal(self._on_multiprocess_event),
                cancel_requested=self._is_cancel_requested,
                fallback_to_single_process=fallback_to_single_process,
            )

        def on_done(result: MultiprocessRunResult) -> None:
            self.lifecycle.transition_complete("Run complete")
            self.surface.set_plan_rows(
                [
                    (
                        entry.table_name,
                        entry.partition_id,
                        f"{entry.start_row}-{entry.end_row}",
                        str(entry.stage),
                        str(entry.assigned_worker),
                        entry.status,
                    )
                    for entry in result.partition_plan
                ]
            )
            self.surface.set_failures_rows(
                [
                    (
                        failure.partition_id,
                        failure.error,
                        str(failure.retry_count),
                        failure.action,
                    )
                    for failure in result.failures
                ]
            )

            csv_count = len(result.strategy_result.csv_paths)
            sqlite_rows = sum(result.strategy_result.sqlite_counts.values())
            self._notify(
                f"Run complete: rows={result.total_rows}, csv_files={csv_count}, sqlite_rows={sqlite_rows}, fallback={'yes' if result.fallback_used else 'no'}.",
                level="success",
                duration_ms=4200,
            )
            self._append_history("run_complete", result.mode, result.fallback_used, result.total_rows)

        label = "Running with fallback..." if fallback_to_single_process else "Running..."
        self.lifecycle.run_async(
            after=self.after,
            worker=worker,
            on_done=lambda payload: on_done(payload),
            on_failed=self._on_run_failed,
            on_cancelled=self._on_run_cancelled,
            phase_label=label,
            cancel_exceptions=(MultiprocessRunCancelled,),
            dispatcher=self.ui_dispatch,
        )

    def _save_profile(self) -> None:
        model = self._sync_viewmodel_from_vars()
        output_path = run_hooks.filedialog.asksaveasfilename(
            title="Save Run Center v2 config JSON",
            defaultextension=".json",
            initialfile=f"{model.profile_name}.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if output_path == "":
            self.shell.set_status("Save config cancelled.")
            return

        payload = run_center_payload(model)
        try:
            Path(output_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:
            self.error_surface.emit(
                location="Save config",
                issue=f"could not write config file ({exc})",
                hint="choose a writable output path",
                mode="mixed",
            )
            return
        self._notify(f"Saved config to {output_path}.", level="success", duration_ms=3200)

    def _load_profile(self) -> None:
        input_path = run_hooks.filedialog.askopenfilename(
            title="Load Run Center v2 config JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if input_path == "":
            self.shell.set_status("Load config cancelled.")
            return
        try:
            payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.error_surface.emit(
                location="Load config",
                issue=f"failed to read JSON ({exc})",
                hint="choose a valid JSON config file",
                mode="mixed",
            )
            return
        if not isinstance(payload, dict):
            self.error_surface.emit(
                location="Load config",
                issue="config JSON must be an object",
                hint="store config fields in a JSON object",
                mode="mixed",
            )
            return

        apply_run_center_payload(self.view_model, payload)
        self.surface.sync_vars_from_model()
        self._notify(f"Loaded config from {input_path}.", level="success", duration_ms=3200)



__all__ = ["RunCenterV2Screen"]
