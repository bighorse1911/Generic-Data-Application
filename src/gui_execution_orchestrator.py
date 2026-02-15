from __future__ import annotations

import json
import os
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk

from src.config import AppConfig
from src.gui_kit.error_surface import ErrorSurface
from src.gui_kit.error_surface import show_error_dialog
from src.gui_kit.error_surface import show_warning_dialog
from src.gui_kit.run_commands import apply_execution_run_config_payload
from src.gui_kit.run_commands import build_config_from_model
from src.gui_kit.run_commands import build_profile_from_model
from src.gui_kit.run_commands import execution_run_config_payload
from src.gui_kit.run_commands import run_build_partition_plan
from src.gui_kit.run_commands import run_generation_multiprocess
from src.gui_kit.run_lifecycle import RunLifecycleController
from src.gui_kit.run_models import RunWorkflowViewModel
from src.gui_kit.ui_dispatch import UIDispatcher
from src.gui_tools.run_workflow_view import RunWorkflowCapabilities
from src.gui_tools.run_workflow_view import RunWorkflowSurface
from src.multiprocessing_runtime import EXECUTION_MODES
from src.multiprocessing_runtime import MultiprocessEvent
from src.multiprocessing_runtime import MultiprocessRunCancelled
from src.multiprocessing_runtime import MultiprocessRunResult
from src.multiprocessing_runtime import PartitionFailure
from src.multiprocessing_runtime import PartitionPlanEntry
from src.multiprocessing_runtime import WorkerStatus
from src.multiprocessing_runtime import build_worker_status_snapshot
from src.schema_project_io import load_project_from_json


class ExecutionOrchestratorScreen(ttk.Frame):
    """Multiprocessing run planner/monitor with retry and fallback controls."""

    def __init__(self, parent: tk.Widget, app: object, cfg: AppConfig) -> None:
        super().__init__(parent, padding=16)
        self.app = app
        self.cfg = cfg
        self.project = None
        self._loaded_schema_path = ""

        cpu_count = max(1, int(os.cpu_count() or 1))
        default_workers = max(1, min(4, cpu_count))
        self.model = RunWorkflowViewModel(
            execution_mode=EXECUTION_MODES[1],
            worker_count=str(default_workers),
            max_inflight_chunks=str(default_workers * 2),
        )

        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 8))
        ttk.Button(header, text="\u2190 Back", command=lambda: self.app.go_home()).pack(side="left")
        ttk.Label(header, text="Execution Orchestrator", font=("Segoe UI", 16, "bold")).pack(side="left", padx=(10, 0))

        self.surface = RunWorkflowSurface(
            self,
            model=self.model,
            capabilities=RunWorkflowCapabilities(
                build_plan=True,
                start_run=True,
                start_fallback=True,
                workers_tab=True,
                failures_tab=True,
                show_status_label=True,
            ),
        )
        self.surface.pack(fill="both", expand=True)
        self.surface.set_status("Load a schema and build a partition plan.")

        self.surface.browse_btn.configure(command=self._browse_schema_path)
        self.surface.load_schema_btn.configure(command=self._load_schema)
        self.surface.build_plan_btn.configure(command=self._build_plan)
        self.surface.start_run_btn.configure(command=self._start_run)
        self.surface.start_fallback_btn.configure(command=lambda: self._start_run(fallback_to_single_process=True))
        self.surface.cancel_run_btn.configure(command=self._cancel_run)
        self.surface.save_btn.configure(text="Save run config...", command=self._save_run_config)
        self.surface.load_btn.configure(text="Load run config...", command=self._load_run_config)

        self.partition_tree = self.surface.partition_tree
        self.worker_tree = self.surface.worker_tree
        self.failures_tree = self.surface.failures_tree
        self.start_run_btn = self.surface.start_run_btn
        self.start_fallback_btn = self.surface.start_fallback_btn
        self.cancel_run_btn = self.surface.cancel_run_btn
        self.status_var = self.surface.status_var
        self.live_phase_var = self.surface.live_phase_var
        self.live_rows_var = self.surface.live_rows_var
        self.live_eta_var = self.surface.live_eta_var
        self.live_progress = self.surface.live_progress

        self.error_surface = ErrorSurface(
            context="Execution Orchestrator",
            dialog_title="Execution orchestrator error",
            warning_title="Execution orchestrator warning",
            show_dialog=show_error_dialog,
            show_warning=show_warning_dialog,
            set_status=self.surface.set_status,
            set_inline=self.surface.set_inline_error,
        )
        self.ui_dispatch = UIDispatcher.from_widget(self)

        self.lifecycle = RunLifecycleController(
            set_phase=self.live_phase_var.set,
            set_rows=self.live_rows_var.set,
            set_eta=self.live_eta_var.set,
            set_progress=lambda value: self.live_progress.configure(value=value),
            set_status=self.surface.set_status,
            action_buttons=[self.surface.build_plan_btn, self.surface.start_run_btn, self.surface.start_fallback_btn],
            cancel_button=self.surface.cancel_run_btn,
        )

    def _sync_model(self) -> RunWorkflowViewModel:
        return self.surface.sync_model_from_vars()

    def _browse_schema_path(self) -> None:
        path = filedialog.askopenfilename(
            title="Select schema project JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.surface.schema_path_var.set(path)

    def _load_schema(self) -> bool:
        model = self._sync_model()
        if model.schema_path == "":
            self.error_surface.emit(
                location="Schema path",
                issue="path is required",
                hint="browse to an existing schema project JSON file",
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
        self.surface.clear_tree(self.partition_tree)
        self.surface.clear_tree(self.worker_tree)
        self.surface.clear_tree(self.failures_tree)
        self.surface.set_status(f"Loaded schema '{loaded.name}' with {len(loaded.tables)} tables.")
        self.surface.set_inline_error("")
        return True

    def _ensure_project(self) -> bool:
        model = self._sync_model()
        if self.project is None:
            return self._load_schema()
        if model.schema_path == "":
            return True
        if model.schema_path != self._loaded_schema_path:
            return self._load_schema()
        return True

    def _populate_partition_tree(self, entries: list[PartitionPlanEntry]) -> None:
        self.surface.clear_tree(self.partition_tree)
        for entry in entries:
            self.partition_tree.insert(
                "",
                "end",
                values=(
                    entry.table_name,
                    entry.partition_id,
                    f"{entry.start_row}-{entry.end_row}",
                    str(entry.stage),
                    str(entry.assigned_worker),
                    entry.status,
                ),
            )

    def _populate_worker_tree(self, workers: dict[int, WorkerStatus]) -> None:
        self.surface.clear_tree(self.worker_tree)
        for worker_id in sorted(workers):
            worker = workers[worker_id]
            heartbeat = "--"
            if worker.last_heartbeat_epoch > 0:
                heartbeat = time.strftime("%H:%M:%S", time.localtime(worker.last_heartbeat_epoch))
            current = ""
            if worker.current_partition_id:
                current = f"{worker.current_table} / {worker.current_partition_id}"
            self.worker_tree.insert(
                "",
                "end",
                values=(
                    str(worker.worker_id),
                    current,
                    str(worker.rows_processed),
                    f"{worker.throughput_rows_per_sec:.1f}",
                    f"{worker.memory_mb:.3f}",
                    heartbeat,
                    worker.state,
                ),
            )

    def _append_failure(self, failure: PartitionFailure) -> None:
        self.failures_tree.insert(
            "",
            "end",
            values=(
                failure.partition_id,
                failure.error,
                str(failure.retry_count),
                failure.action,
            ),
        )

    def _build_plan(self) -> None:
        if self.lifecycle.state.is_running:
            return
        if not self._ensure_project():
            return
        assert self.project is not None
        model = self._sync_model()
        try:
            plan = run_build_partition_plan(self.project, model)
            config = build_config_from_model(model)
            workers = build_worker_status_snapshot(config)
        except ValueError as exc:
            self.error_surface.emit_exception_actionable(
                exc,
                location="Build partition plan",
                hint="review multiprocess settings and retry",
                mode="mixed",
            )
            return

        self._populate_partition_tree(plan)
        self._populate_worker_tree(workers)
        total_rows = sum(entry.rows_in_partition for entry in plan)
        self.surface.set_status(f"Partition plan ready: partitions={len(plan)}, rows={total_rows}, workers={len(workers)}.")
        self.surface.set_focus("plan")

    def _cancel_run(self) -> None:
        self.lifecycle.request_cancel("Cancellation requested. Waiting for current task to stop...")

    def _is_cancel_requested(self) -> bool:
        return self.lifecycle.is_cancel_requested()

    def _on_runtime_event(self, event: MultiprocessEvent) -> None:
        self.lifecycle.handle_multiprocess_event(event)
        if event.kind == "partition_failed" and event.partition_id:
            self.failures_tree.insert(
                "",
                "end",
                values=(event.partition_id, event.message, str(event.retry_count), "retry"),
            )

    def _on_run_failed(self, message: str) -> None:
        self.lifecycle.transition_failed(message, phase="Failed")
        self.error_surface.emit_formatted(message, mode="mixed")

    def _on_run_cancelled(self, message: str) -> None:
        self.lifecycle.transition_cancelled(message, phase="Cancelled")
        self.live_phase_var.set("Run cancelled.")
        self.live_eta_var.set("ETA: cancelled")

    def _on_run_done(self, result: MultiprocessRunResult) -> None:
        self.lifecycle.transition_complete("Complete")
        self._populate_partition_tree(result.partition_plan)
        self._populate_worker_tree(result.worker_status)
        self.surface.clear_tree(self.failures_tree)
        for failure in result.failures:
            self._append_failure(failure)

        csv_count = len(result.strategy_result.csv_paths)
        sqlite_rows = sum(result.strategy_result.sqlite_counts.values())
        fallback_text = "yes" if result.fallback_used else "no"
        self.surface.set_status(
            (
                "Run complete: "
                f"rows={result.total_rows}, csv_files={csv_count}, sqlite_rows={sqlite_rows}, "
                f"fallback={fallback_text}."
            )
        )

    def _start_run(self, fallback_to_single_process: bool = False) -> None:
        if not self._ensure_project():
            return
        assert self.project is not None

        model = self._sync_model()
        try:
            profile = build_profile_from_model(model)
            build_config_from_model(model)
        except ValueError as exc:
            self.error_surface.emit_exception_actionable(
                exc,
                location="Start run",
                hint="fix run configuration values and retry",
                mode="mixed",
            )
            return

        output_mode = profile.output_mode
        output_csv_folder: str | None = None
        output_sqlite_path: str | None = None

        if output_mode in {"csv", "all"}:
            output_csv_folder = filedialog.askdirectory(title="Choose output folder for CSV export")
            if output_csv_folder in {None, ""}:
                self.surface.set_status("Run cancelled (no CSV output folder selected).")
                return

        if output_mode in {"sqlite", "all"}:
            output_sqlite_path = filedialog.asksaveasfilename(
                title="Choose SQLite output path",
                defaultextension=".db",
                filetypes=[("SQLite DB", "*.db"), ("All files", "*.*")],
                initialfile="execution_orchestrator.db",
            )
            if output_sqlite_path in {None, ""}:
                self.surface.set_status("Run cancelled (no SQLite output path selected).")
                return

        def worker() -> MultiprocessRunResult:
            return run_generation_multiprocess(
                self.project,
                model,
                output_csv_folder=output_csv_folder,
                output_sqlite_path=output_sqlite_path,
                on_event=self.ui_dispatch.marshal(self._on_runtime_event),
                cancel_requested=self._is_cancel_requested,
                fallback_to_single_process=fallback_to_single_process,
            )

        label = "Running with fallback..." if fallback_to_single_process else "Running..."
        self.lifecycle.run_async(
            after=self.after,
            worker=worker,
            on_done=lambda result: self._on_run_done(result),
            on_failed=self._on_run_failed,
            on_cancelled=self._on_run_cancelled,
            phase_label=label,
            cancel_exceptions=(MultiprocessRunCancelled,),
            dispatcher=self.ui_dispatch,
        )

    def _save_run_config(self) -> None:
        model = self._sync_model()
        try:
            payload = execution_run_config_payload(model)
        except ValueError as exc:
            self.error_surface.emit_exception_actionable(
                exc,
                location="Save run config",
                hint="fix invalid run configuration fields and retry",
                mode="mixed",
            )
            return

        output_path = filedialog.asksaveasfilename(
            title="Save execution run config JSON",
            defaultextension=".json",
            initialfile="execution_orchestrator_config.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if output_path == "":
            self.surface.set_status("Save run config cancelled.")
            return

        try:
            Path(output_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:
            self.error_surface.emit(
                location="Save run config",
                issue=f"could not write config file ({exc})",
                hint="choose a writable output path",
                mode="mixed",
            )
            return

        self.surface.set_status(f"Saved run config to {output_path}.")

    def _load_run_config(self) -> None:
        config_path = filedialog.askopenfilename(
            title="Load execution run config JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if config_path == "":
            self.surface.set_status("Load run config cancelled.")
            return

        try:
            payload = json.loads(Path(config_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.error_surface.emit(
                location="Load run config",
                issue=f"failed to read config JSON ({exc})",
                hint="choose a valid JSON config file",
                mode="mixed",
            )
            return

        if not isinstance(payload, dict):
            self.error_surface.emit(
                location="Load run config",
                issue="config JSON must be an object",
                hint="store profile and multiprocess fields in a JSON object",
                mode="mixed",
            )
            return

        try:
            apply_execution_run_config_payload(self.model, payload)
            build_profile_from_model(self.model)
            build_config_from_model(self.model)
        except ValueError as exc:
            self.error_surface.emit_exception_actionable(
                exc,
                location="Load run config",
                hint="correct payload values and retry",
                mode="mixed",
            )
            return

        self.surface.sync_vars_from_model()
        self.surface.set_status(f"Loaded run config from {config_path}.")
