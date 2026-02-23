from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.config import AppConfig
from src.gui_performance_workbench_base import PerformanceWorkbenchBase
from src.gui_kit.error_surface import ErrorSurface
from src.gui_kit.error_surface import show_error_dialog
from src.gui_kit.error_surface import show_warning_dialog
from src.gui_kit.feedback import ToastCenter
from src.gui_kit.run_lifecycle import RunLifecycleController
from src.gui_kit.run_models import RunWorkflowViewModel
from src.gui_kit.shortcuts import ShortcutManager
from src.gui_kit.ui_dispatch import UIDispatcher
from src.gui_kit.accessibility import FocusController
from src.gui_tools.run_workflow_view import RunWorkflowCapabilities
from src.gui_tools.run_workflow_view import RunWorkflowSurface
from src.gui_v2_redesign import V2ShellFrame


class PerformanceWorkbenchV2Screen(PerformanceWorkbenchBase):
    """Native v2 route for strategy benchmark and generation workflows."""

    def __init__(self, parent: tk.Widget, app: object, cfg: AppConfig) -> None:
        ttk.Frame.__init__(self, parent)
        self.app = app
        self.cfg = cfg
        self.project = None
        self._loaded_schema_path = ""

        self.shell = V2ShellFrame(self, title="Performance Workbench v2", on_back=lambda: self.app.show_screen("home_v2"))
        self.shell.pack(fill="both", expand=True)
        self.shell.add_header_action("Run Center", lambda: self.app.show_screen("run_center_v2"))
        self.shell.add_header_action("Home v2", lambda: self.app.show_screen("home_v2"))
        self.shell.add_header_action("Notifications", self._show_notifications_history)

        self.shell.add_nav_button("config", "Config", lambda: self._set_focus("config"))
        self.shell.add_nav_button("diagnostics", "Diagnostics", lambda: self._set_focus("diagnostics"))
        self.shell.add_nav_button("plan", "Chunk Plan", lambda: self._set_focus("plan"))
        self.shell.add_nav_button("actions", "Actions", lambda: self._set_focus("actions"))
        self.shell.set_nav_active("config")

        self.model = RunWorkflowViewModel()
        self.surface = RunWorkflowSurface(
            self.shell.workspace,
            model=self.model,
            capabilities=RunWorkflowCapabilities(
                estimate=True,
                build_plan=True,
                benchmark=True,
                generate_strategy=True,
                show_status_label=False,
            ),
            status_callback=self.shell.set_status,
        )
        self.surface.pack(fill="both", expand=True, padx=10, pady=10)

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
            set_status=self.shell.set_status,
            set_inline=self.surface.set_inline_error,
        )
        self.ui_dispatch = UIDispatcher.from_widget(self)

        self.lifecycle = RunLifecycleController(
            set_phase=self.live_phase_var.set,
            set_rows=self.live_rows_var.set,
            set_eta=self.live_eta_var.set,
            set_progress=lambda value: self.live_progress.configure(value=value),
            set_status=self.shell.set_status,
            action_buttons=[self.surface.estimate_btn, self.surface.build_plan_btn, self.surface.run_benchmark_btn, self.surface.run_generate_btn],
            cancel_button=self.surface.cancel_run_btn,
        )
        self.shortcut_manager = ShortcutManager(self)
        self.focus_controller = FocusController(self)
        self.toast_center = ToastCenter(self)
        self._register_focus_anchors()
        self._register_shortcuts()

        self.shell.set_inspector(
            "Workbench Notes",
            [
                "Estimate and chunk-plan actions remain deterministic.",
                "Benchmark/generate strategy runs preserve runtime semantics.",
            ],
        )
        self.shell.set_status("Performance Workbench v2 ready.")

    def _set_focus(self, key: str) -> None:
        self.shell.set_nav_active(key)
        if key in {"diagnostics", "plan"}:
            self.surface.set_focus(key)
        elif key == "actions":
            if self.surface.estimate_btn is not None:
                self.surface.estimate_btn.focus_set()
        self.shell.set_status(f"Performance Workbench v2: focus set to {key}.")

    def _show_shortcuts_help(self) -> None:
        self.shortcut_manager.show_help_dialog(title="Performance Workbench v2 Shortcuts")
