from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.config import AppConfig
from src.gui_route_policy import ORCHESTRATOR_V2_ROUTE
from src.gui_route_policy import PERFORMANCE_V2_ROUTE
from src.gui_kit.accessibility import FocusController
from src.gui_kit.error_surface import ErrorSurface
from src.gui_kit.error_surface import show_error_dialog
from src.gui_kit.error_surface import show_warning_dialog
from src.gui_kit.feedback import ToastCenter
from src.gui_kit.run_lifecycle import RunLifecycleController
from src.gui_kit.shortcuts import ShortcutManager
from src.gui_kit.ui_dispatch import UIDispatcher
from src.gui_tools.run_workflow_view import RunWorkflowCapabilities
from src.gui_tools.run_workflow_view import RunWorkflowSurface
from src.gui.v2.routes import run_center_io
from src.gui.v2.routes import run_center_nav
from src.gui.v2.routes import run_center_runs
from src.gui.v2.routes.shell_impl import V2ShellFrame
from src.gui.v2.routes.theme_shared import V2_BG
from src.gui_v2.viewmodels import RunCenterViewModel
from src.multiprocessing_runtime import MultiprocessEvent
from src.performance_scaling import RuntimeEvent


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
        return run_center_nav.on_show(self)

    def on_hide(self) -> None:
        return run_center_nav.on_hide(self)

    def _register_focus_anchors(self) -> None:
        return run_center_nav._register_focus_anchors(self)

    def _register_shortcuts(self) -> None:
        return run_center_nav._register_shortcuts(self)

    def _focus_next_anchor(self) -> None:
        return run_center_nav._focus_next_anchor(self)

    def _focus_previous_anchor(self) -> None:
        return run_center_nav._focus_previous_anchor(self)

    def _cancel_if_running(self) -> None:
        return run_center_nav._cancel_if_running(self)

    def _show_shortcuts_help(self) -> None:
        return run_center_nav._show_shortcuts_help(self)

    def _show_notifications_history(self) -> None:
        return run_center_nav._show_notifications_history(self)

    def _notify(self, message: str, *, level: str = "info", duration_ms: int | None = None) -> None:
        return run_center_nav._notify(self, message, level=level, duration_ms=duration_ms)

    def _set_inspector_for_config(self) -> None:
        return run_center_nav._set_inspector_for_config(self)

    def _set_focus(self, key: str) -> None:
        return run_center_nav._set_focus(self, key)

    def _sync_viewmodel_from_vars(self) -> RunCenterViewModel:
        return run_center_io._sync_viewmodel_from_vars(self)

    def _browse_schema_path(self) -> None:
        return run_center_io._browse_schema_path(self)

    def _load_schema(self) -> bool:
        return run_center_io._load_schema(self)

    def _ensure_project(self) -> bool:
        return run_center_io._ensure_project(self)

    def _save_profile(self) -> None:
        return run_center_io._save_profile(self)

    def _load_profile(self) -> None:
        return run_center_io._load_profile(self)

    def _clear_tree(self, tree: ttk.Treeview | None) -> None:
        return run_center_runs._clear_tree(self, tree)

    def _set_running(self, running: bool, phase: str) -> None:
        return run_center_runs._set_running(self, running, phase)

    def _cancel_run(self) -> None:
        return run_center_runs._cancel_run(self)

    def _is_cancel_requested(self) -> bool:
        return run_center_runs._is_cancel_requested(self)

    def _append_history(self, status: str, mode: str, fallback: bool, rows: int) -> None:
        return run_center_runs._append_history(self, status, mode, fallback, rows)

    def _on_runtime_event(self, event: RuntimeEvent) -> None:
        return run_center_runs._on_runtime_event(self, event)

    def _on_multiprocess_event(self, event: MultiprocessEvent) -> None:
        return run_center_runs._on_multiprocess_event(self, event)

    def _on_run_failed(self, message: str) -> None:
        return run_center_runs._on_run_failed(self, message)

    def _on_run_cancelled(self, message: str) -> None:
        return run_center_runs._on_run_cancelled(self, message)

    def _run_estimate(self) -> None:
        return run_center_runs._run_estimate(self)

    def _run_build_plan(self) -> None:
        return run_center_runs._run_build_plan(self)

    def _start_benchmark(self) -> None:
        return run_center_runs._start_benchmark(self)

    def _start_generation(self, fallback_to_single_process: bool = False) -> None:
        return run_center_runs._start_generation(
            self,
            fallback_to_single_process=fallback_to_single_process,
        )


__all__ = ["RunCenterV2Screen"]
