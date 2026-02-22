from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

from src.config import AppConfig
from src.gui_execution_orchestrator_base import ExecutionOrchestratorBase
from src.gui_kit.accessibility import FocusController
from src.gui_kit.error_surface import ErrorSurface
from src.gui_kit.error_surface import show_error_dialog
from src.gui_kit.error_surface import show_warning_dialog
from src.gui_kit.run_lifecycle import RunLifecycleController
from src.gui_kit.run_models import RunWorkflowViewModel
from src.gui_kit.shortcuts import ShortcutManager
from src.gui_kit.ui_dispatch import UIDispatcher
from src.gui_tools.run_workflow_view import RunWorkflowCapabilities
from src.gui_tools.run_workflow_view import RunWorkflowSurface
from src.gui_v2_redesign import V2ShellFrame
from src.multiprocessing_runtime import EXECUTION_MODES


class ExecutionOrchestratorV2Screen(ExecutionOrchestratorBase):
    """Native v2 route for multiprocess orchestration planning and execution."""

    def __init__(self, parent: tk.Widget, app: object, cfg: AppConfig) -> None:
        ttk.Frame.__init__(self, parent)
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

        self.shell = V2ShellFrame(self, title="Execution Orchestrator v2", on_back=lambda: self.app.show_screen("home_v2"))
        self.shell.pack(fill="both", expand=True)
        self.shell.add_header_action("Run Center", lambda: self.app.show_screen("run_center_v2"))
        self.shell.add_header_action("Home v2", lambda: self.app.show_screen("home_v2"))

        self.shell.add_nav_button("config", "Config", lambda: self._set_focus("config"))
        self.shell.add_nav_button("plan", "Plan", lambda: self._set_focus("plan"))
        self.shell.add_nav_button("workers", "Workers", lambda: self._set_focus("workers"))
        self.shell.add_nav_button("failures", "Failures", lambda: self._set_focus("failures"))
        self.shell.add_nav_button("actions", "Actions", lambda: self._set_focus("actions"))
        self.shell.set_nav_active("config")

        self.surface = RunWorkflowSurface(
            self.shell.workspace,
            model=self.model,
            capabilities=RunWorkflowCapabilities(
                build_plan=True,
                start_run=True,
                start_fallback=True,
                workers_tab=True,
                failures_tab=True,
                show_status_label=False,
            ),
            status_callback=self.shell.set_status,
        )
        self.surface.pack(fill="both", expand=True, padx=10, pady=10)
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
            action_buttons=[self.surface.build_plan_btn, self.surface.start_run_btn, self.surface.start_fallback_btn],
            cancel_button=self.surface.cancel_run_btn,
        )
        self.shortcut_manager = ShortcutManager(self)
        self.focus_controller = FocusController(self)
        self._register_focus_anchors()
        self._register_shortcuts()

        self.shell.set_inspector(
            "Orchestrator Notes",
            [
                "Build deterministic FK-stage partition plans.",
                "Monitor worker/failure tables during live execution.",
            ],
        )
        self.shell.set_status("Execution Orchestrator v2 ready.")

    def _set_focus(self, key: str) -> None:
        self.shell.set_nav_active(key)
        if key in {"plan", "workers", "failures"}:
            self.surface.set_focus(key)
        elif key == "actions":
            if self.surface.build_plan_btn is not None:
                self.surface.build_plan_btn.focus_set()
        self.shell.set_status(f"Execution Orchestrator v2: focus set to {key}.")

    def _show_shortcuts_help(self) -> None:
        self.shortcut_manager.show_help_dialog(title="Execution Orchestrator v2 Shortcuts")
