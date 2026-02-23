from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk

from src.config import AppConfig
from src.gui_kit.accessibility import FocusController
from src.gui_kit.error_surface import ErrorSurface
from src.gui_kit.error_surface import show_error_dialog
from src.gui_kit.error_surface import show_warning_dialog
from src.gui_kit.feedback import ToastCenter
from src.gui_kit.run_commands import apply_performance_profile_payload
from src.gui_kit.run_commands import build_profile_from_model
from src.gui_kit.run_commands import performance_profile_payload
from src.gui_kit.run_commands import run_benchmark as run_shared_benchmark
from src.gui_kit.run_commands import run_build_chunk_plan
from src.gui_kit.run_commands import run_estimate as run_shared_estimate
from src.gui_kit.run_commands import run_generation_strategy
from src.gui_kit.run_lifecycle import RunLifecycleController
from src.gui_kit.run_models import RunWorkflowViewModel
from src.gui_kit.shortcuts import ShortcutManager
from src.gui_kit.ui_dispatch import UIDispatcher
from src.gui_tools.run_workflow_view import RunWorkflowCapabilities
from src.gui_tools.run_workflow_view import RunWorkflowSurface
from src.performance_scaling import BenchmarkResult
from src.performance_scaling import ChunkPlanEntry
from src.performance_scaling import PerformanceRunCancelled
from src.performance_scaling import RuntimeEvent
from src.performance_scaling import StrategyRunResult
from src.schema_project_io import load_project_from_json
class PerformanceWorkbenchBase(ttk.Frame):
    """Shared performance workbench behavior used by v2 GUI routes."""

    def __init__(self, parent: tk.Widget, app: "App", cfg: AppConfig) -> None:
        super().__init__(parent, padding=16)
        self.app = app
        self.cfg = cfg
        self.project = None
        self._loaded_schema_path = ""

        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 8))
        ttk.Button(header, text="\u2190 Back", command=self.app.go_home).pack(side="left")
        ttk.Label(header, text="Performance Workbench", font=("Segoe UI", 16, "bold")).pack(side="left", padx=(10, 0))
        ttk.Button(header, text="Notifications", command=self._show_notifications_history).pack(side="right", padx=(0, 6))
        ttk.Button(header, text="Shortcuts", command=self._show_shortcuts_help).pack(side="right")

        subtitle = ttk.Label(
            self,
            justify="left",
            wraplength=940,
            text=(
                "Configure performance profile values, validate FK-safe row overrides, and estimate workload "
                "memory/time before full generation."
            ),
        )
        subtitle.pack(anchor="w", pady=(0, 10))

        self.model = RunWorkflowViewModel()
        self.surface = RunWorkflowSurface(
            self,
            model=self.model,
            capabilities=RunWorkflowCapabilities(
                estimate=True,
                build_plan=True,
                benchmark=True,
                generate_strategy=True,
                show_status_label=True,
            ),
        )
        self.surface.pack(fill="both", expand=True)
        self.surface.set_status("Load a schema and estimate workload strategy.")
        self.toast_center = ToastCenter(self)

        self.surface.browse_btn.configure(command=self._browse_schema_path)
        self.surface.load_schema_btn.configure(command=self._load_schema)
        self.surface.estimate_btn.configure(command=self._estimate_workload)
        self.surface.build_plan_btn.configure(command=self._build_chunk_plan)
        self.surface.run_benchmark_btn.configure(command=self._start_run_benchmark)
        self.surface.run_generate_btn.configure(command=self._start_generate_with_strategy)
        self.surface.cancel_run_btn.configure(command=self._cancel_run)
        self.surface.save_btn.configure(text="Save profile...", command=self._save_profile)
        self.surface.load_btn.configure(text="Load profile...", command=self._load_profile)

        self.diagnostics_tree = self.surface.diagnostics_tree
        self.chunk_plan_tree = self.surface.chunk_plan_tree
        self.run_benchmark_btn = self.surface.run_benchmark_btn
        self.run_generate_btn = self.surface.run_generate_btn
        self.cancel_run_btn = self.surface.cancel_run_btn
        self.status_var = self.surface.status_var
        self.live_phase_var = self.surface.live_phase_var
        self.live_rows_var = self.surface.live_rows_var
        self.live_eta_var = self.surface.live_eta_var
        self.live_progress = self.surface.live_progress

        self.error_surface = ErrorSurface(
            context="Performance Workbench",
            dialog_title="Performance workbench error",
            warning_title="Performance workbench warning",
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
            action_buttons=[self.surface.estimate_btn, self.surface.build_plan_btn, self.surface.run_benchmark_btn, self.surface.run_generate_btn],
            cancel_button=self.surface.cancel_run_btn,
        )
        self.shortcut_manager = ShortcutManager(self)
        self.focus_controller = FocusController(self)
        self._register_focus_anchors()
        self._register_shortcuts()

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
            lambda: self.surface.estimate_btn,
            description="Run action controls",
        )
        self.focus_controller.add_anchor(
            "diagnostics",
            lambda: self.diagnostics_tree,
            description="Diagnostics table",
        )
        self.focus_controller.add_anchor(
            "plan",
            lambda: self.chunk_plan_tree,
            description="Chunk plan table",
        )
        self.focus_controller.set_default_anchor("schema_path")

    def _register_shortcuts(self) -> None:
        self.shortcut_manager.register("<F1>", "Open shortcuts help", self._show_shortcuts_help)
        self.shortcut_manager.register("<F6>", "Focus next major section", self._focus_next_anchor)
        self.shortcut_manager.register("<Shift-F6>", "Focus previous major section", self._focus_previous_anchor)
        self.shortcut_manager.register_ctrl_cmd("b", "Browse schema path", self._browse_schema_path)
        self.shortcut_manager.register_ctrl_cmd("l", "Load schema", self._load_schema)
        self.shortcut_manager.register_ctrl_cmd("s", "Save profile", self._save_profile)
        self.shortcut_manager.register_ctrl_cmd("o", "Load profile", self._load_profile)
        self.shortcut_manager.register("<F5>", "Estimate workload", self._estimate_workload)
        self.shortcut_manager.register_ctrl_cmd("Return", "Run benchmark", self._start_run_benchmark)
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
        self.shortcut_manager.show_help_dialog(title="Performance Workbench Shortcuts")

    def _show_notifications_history(self) -> None:
        if hasattr(self, "toast_center"):
            self.toast_center.show_history_dialog(title="Performance Workbench Notifications")

    def _notify(self, message: str, *, level: str = "info", duration_ms: int | None = None) -> None:
        text = str(message).strip()
        if text == "":
            return
        self.surface.set_status(text)
        if hasattr(self, "toast_center"):
            self.toast_center.notify(text, level=level, duration_ms=duration_ms)

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
        self.surface.clear_tree(self.diagnostics_tree)
        self.surface.clear_tree(self.chunk_plan_tree)
        self.surface.set_status(
            f"Loaded schema '{loaded.name}' with {len(loaded.tables)} tables. Configure profile and estimate workload."
        )
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

    def _populate_estimates(self, estimates: list[object]) -> None:
        rows: list[tuple[str, str, str, str, str, str, str]] = []
        for estimate in estimates:
            rows.append(
                (
                    estimate.table_name,
                    str(estimate.estimated_rows),
                    f"{estimate.estimated_memory_mb:.3f}",
                    f"{estimate.estimated_write_mb:.3f}",
                    f"{estimate.estimated_seconds:.3f}",
                    estimate.risk_level,
                    estimate.recommendation,
                )
            )
        self.surface.set_diagnostics_rows(rows)

    def _populate_chunk_plan(self, entries: list[ChunkPlanEntry]) -> None:
        rows: list[tuple[str, str, str, str, str, str]] = []
        for entry in entries:
            partition_id = f"{entry.table_name}|stage={entry.stage}|chunk={entry.chunk_index}"
            rows.append(
                (
                    entry.table_name,
                    partition_id,
                    f"{entry.start_row}-{entry.end_row}",
                    str(entry.stage),
                    "-",
                    "planned",
                )
            )
        self.surface.set_plan_rows(rows)

    def _estimate_workload(self) -> None:
        if self.lifecycle.state.is_running:
            return
        if not self._ensure_project():
            return
        assert self.project is not None
        model = self._sync_model()
        try:
            diagnostics = run_shared_estimate(self.project, model)
        except ValueError as exc:
            self.error_surface.emit_exception_actionable(
                exc,
                location="Estimate workload",
                hint="review workload profile values and retry",
                mode="mixed",
            )
            return
        self._populate_estimates(diagnostics.estimates)
        self._notify(
            "Estimate complete: "
            f"rows={diagnostics.summary.total_rows}, memory={diagnostics.summary.total_memory_mb:.3f} MB, "
            f"write={diagnostics.summary.total_write_mb:.3f} MB, time={diagnostics.summary.total_seconds:.3f} s, "
            f"highest risk={diagnostics.summary.highest_risk}.",
            level="success",
            duration_ms=3600,
        )
        self.surface.set_focus("diagnostics")

    def _build_chunk_plan(self) -> None:
        if self.lifecycle.state.is_running:
            return
        if not self._ensure_project():
            return
        assert self.project is not None
        model = self._sync_model()
        try:
            plan_entries = run_build_chunk_plan(self.project, model)
        except ValueError as exc:
            self.error_surface.emit_exception_actionable(
                exc,
                location="Build chunk plan",
                hint="review profile settings and retry",
                mode="mixed",
            )
            return
        self._populate_chunk_plan(plan_entries)
        total_rows = sum(entry.rows_in_chunk for entry in plan_entries)
        max_stage = max((entry.stage for entry in plan_entries), default=0)
        self._notify(
            f"Chunk plan ready: tables={len({e.table_name for e in plan_entries})}, "
            f"chunks={len(plan_entries)}, rows={total_rows}, max stage={max_stage}.",
            level="success",
            duration_ms=3600,
        )
        self.surface.set_focus("plan")

    def _cancel_run(self) -> None:
        self.lifecycle.request_cancel("Cancellation requested. Waiting for current step to finish...")

    def _is_cancel_requested(self) -> bool:
        return self.lifecycle.is_cancel_requested()

    def _on_runtime_event(self, event: RuntimeEvent) -> None:
        self.lifecycle.handle_runtime_event(event)

    def _on_run_failed(self, message: str) -> None:
        self.lifecycle.transition_failed(message, phase="Failed")
        self.error_surface.emit_formatted(message, mode="mixed")

    def _on_run_cancelled(self, message: str) -> None:
        self.lifecycle.transition_cancelled(message, phase="Cancelled")
        self._on_runtime_event(RuntimeEvent(kind="cancelled", message="Run cancelled by user."))
        self._notify("Run cancelled by user request.", level="warn", duration_ms=3200)

    def _on_benchmark_done(self, result: BenchmarkResult) -> None:
        self.lifecycle.transition_complete("Benchmark complete")
        self._populate_estimates(result.estimates)
        self._populate_chunk_plan(result.chunk_plan)
        self._notify(
            "Benchmark complete: "
            f"tables={len(result.selected_tables)}, chunks={result.chunk_summary.total_chunks}, "
            f"rows={result.chunk_summary.total_rows}, risk={result.estimate_summary.highest_risk}.",
            level="success",
            duration_ms=3800,
        )

    def _on_generate_done(self, result: StrategyRunResult) -> None:
        self.lifecycle.transition_complete("Generation complete")
        csv_count = len(result.csv_paths)
        sqlite_rows = sum(result.sqlite_counts.values())
        self._notify(
            "Generation complete: "
            f"tables={len(result.selected_tables)}, rows={result.total_rows}, "
            f"csv_files={csv_count}, sqlite_rows={sqlite_rows}.",
            level="success",
            duration_ms=4000,
        )

    def _start_run_benchmark(self) -> None:
        if not self._ensure_project():
            return
        assert self.project is not None
        model = self._sync_model()

        def worker() -> BenchmarkResult:
            return run_shared_benchmark(
                self.project,
                model,
                on_event=self.ui_dispatch.marshal(self._on_runtime_event),
                cancel_requested=self._is_cancel_requested,
            )

        self.lifecycle.run_async(
            after=self.after,
            worker=worker,
            on_done=lambda result: self._on_benchmark_done(result),
            on_failed=self._on_run_failed,
            on_cancelled=self._on_run_cancelled,
            phase_label="Running benchmark...",
            cancel_exceptions=(PerformanceRunCancelled,),
            dispatcher=self.ui_dispatch,
        )

    def _start_generate_with_strategy(self) -> None:
        if not self._ensure_project():
            return
        assert self.project is not None
        model = self._sync_model()
        try:
            profile = build_profile_from_model(model)
        except ValueError as exc:
            self.error_surface.emit_exception_actionable(
                exc,
                location="Generate with strategy",
                hint="fix profile fields before running generation",
                mode="mixed",
            )
            return

        output_mode = profile.output_mode
        output_csv_folder: str | None = None
        output_sqlite_path: str | None = None
        if output_mode in {"csv", "all"}:
            output_csv_folder = filedialog.askdirectory(title="Choose output folder for strategy CSV export")
            if output_csv_folder in {None, ""}:
                self.surface.set_status("Generate with strategy cancelled (no CSV output folder).")
                return
        if output_mode in {"sqlite", "all"}:
            output_sqlite_path = filedialog.asksaveasfilename(
                title="Choose SQLite output path for strategy run",
                defaultextension=".db",
                filetypes=[("SQLite DB", "*.db"), ("All files", "*.*")],
                initialfile="performance_strategy.db",
            )
            if output_sqlite_path in {None, ""}:
                self.surface.set_status("Generate with strategy cancelled (no SQLite output path).")
                return

        def worker() -> StrategyRunResult:
            return run_generation_strategy(
                self.project,
                model,
                output_csv_folder=output_csv_folder,
                output_sqlite_path=output_sqlite_path,
                on_event=self.ui_dispatch.marshal(self._on_runtime_event),
                cancel_requested=self._is_cancel_requested,
            )

        self.lifecycle.run_async(
            after=self.after,
            worker=worker,
            on_done=lambda result: self._on_generate_done(result),
            on_failed=self._on_run_failed,
            on_cancelled=self._on_run_cancelled,
            phase_label="Generating with strategy...",
            cancel_exceptions=(PerformanceRunCancelled,),
            dispatcher=self.ui_dispatch,
        )

    def _save_profile(self) -> None:
        model = self._sync_model()
        try:
            profile = build_profile_from_model(model)
            payload = performance_profile_payload(profile)
        except ValueError as exc:
            self.error_surface.emit_exception_actionable(
                exc,
                location="Save profile",
                hint="fix invalid profile values and retry",
                mode="mixed",
            )
            return
        output_path = filedialog.asksaveasfilename(
            title="Save performance profile JSON",
            defaultextension=".json",
            initialfile="performance_profile.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if output_path == "":
            self.surface.set_status("Save profile cancelled.")
            return
        try:
            Path(output_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:
            self.error_surface.emit(
                location="Save profile",
                issue=f"could not write profile file ({exc})",
                hint="choose a writable output path",
                mode="mixed",
            )
            return
        self._notify(f"Saved performance profile to {output_path}.", level="success", duration_ms=3200)

    def _load_profile(self) -> None:
        profile_path = filedialog.askopenfilename(
            title="Load performance profile JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if profile_path == "":
            self.surface.set_status("Load profile cancelled.")
            return
        try:
            payload = json.loads(Path(profile_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.error_surface.emit(
                location="Load profile",
                issue=f"failed to read profile JSON ({exc})",
                hint="choose a valid JSON profile file",
                mode="mixed",
            )
            return
        if not isinstance(payload, dict):
            self.error_surface.emit(
                location="Load profile",
                issue="profile JSON must be an object",
                hint="store profile fields in a JSON object",
                mode="mixed",
            )
            return
        try:
            apply_performance_profile_payload(self.model, payload)
            build_profile_from_model(self.model)
        except ValueError as exc:
            self.error_surface.emit_exception_actionable(
                exc,
                location="Load profile",
                hint="correct the profile payload fields and retry",
                mode="mixed",
            )
            return
        self.surface.sync_vars_from_model()
        self._notify(f"Loaded performance profile from {profile_path}.", level="success", duration_ms=3200)
