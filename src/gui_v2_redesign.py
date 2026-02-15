from __future__ import annotations

import json
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from src.config import AppConfig
from src.gui_route_policy import SCHEMA_PRIMARY_ROUTE
from src.gui_kit.error_surface import ErrorSurface
from src.gui_kit.error_surface import show_error_dialog
from src.gui_kit.error_surface import show_warning_dialog
from src.gui_kit.run_commands import apply_run_center_payload
from src.gui_kit.run_commands import build_profile_from_model
from src.gui_kit.run_commands import run_benchmark as run_shared_benchmark
from src.gui_kit.run_commands import run_build_partition_plan as run_shared_build_partition_plan
from src.gui_kit.run_commands import run_center_payload
from src.gui_kit.run_commands import run_estimate as run_shared_estimate
from src.gui_kit.run_commands import run_generation_multiprocess
from src.gui_kit.run_lifecycle import RunLifecycleController
from src.gui_kit.ui_dispatch import UIDispatcher
from src.gui_tools import ERDDesignerToolFrame
from src.gui_tools import GenerationGuideToolFrame
from src.gui_tools import LocationSelectorToolFrame
from src.gui_tools.run_workflow_view import RunWorkflowCapabilities
from src.gui_tools.run_workflow_view import RunWorkflowSurface
from src.gui_v2.navigation import DirtyRouteGuard
from src.gui_v2.navigation import guarded_navigation
from src.gui_v2.viewmodels import ERDDesignerV2ViewModel
from src.gui_v2.viewmodels import GenerationGuideV2ViewModel
from src.gui_v2.viewmodels import LocationSelectorV2ViewModel
from src.gui_v2.viewmodels import RunCenterViewModel
from src.gui_v2.viewmodels import SchemaStudioViewModel
from src.multiprocessing_runtime import MultiprocessEvent
from src.multiprocessing_runtime import MultiprocessRunCancelled
from src.multiprocessing_runtime import MultiprocessRunResult
from src.performance_scaling import BenchmarkResult
from src.performance_scaling import PerformanceRunCancelled
from src.performance_scaling import RuntimeEvent
from src.schema_project_io import load_project_from_json

V2_BG = "#f4efe6"
V2_PANEL = "#fbf8f1"
V2_NAV_BG = "#14334f"
V2_NAV_ACTIVE = "#c76d2a"
V2_HEADER_BG = "#0f2138"
V2_INSPECTOR_BG = "#e9deca"


def _v2_error(location: str, issue: str, hint: str) -> str:
    return f"Run Center v2 / {location}: {issue}. Fix: {hint}."


class _BackToRouteAdapter:
    """Adapter so shared tool frames can call app.go_home() to a target route."""

    def __init__(self, navigate) -> None:
        self._navigate = navigate

    def go_home(self) -> None:
        self._navigate()


class V2ShellFrame(tk.Frame):
    """Shared V2 shell frame with nav rail, workspace, inspector, and status strip."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        title: str,
        on_back,
    ) -> None:
        super().__init__(parent, bg=V2_BG)
        self._nav_buttons: dict[str, tk.Button] = {}

        self.header = tk.Frame(self, bg=V2_HEADER_BG, height=56)
        self.header.pack(fill="x", padx=12, pady=(12, 8))
        self.header.pack_propagate(False)

        self.back_btn = tk.Button(
            self.header,
            text="Back",
            command=on_back,
            bg="#d9d2c4",
            fg="#1f1f1f",
            relief="flat",
            padx=12,
            pady=6,
        )
        self.back_btn.pack(side="left", padx=(8, 10), pady=8)

        self.title_label = tk.Label(
            self.header,
            text=title,
            bg=V2_HEADER_BG,
            fg="#f5f5f5",
            font=("Cambria", 16, "bold"),
        )
        self.title_label.pack(side="left", pady=8)

        self.header_actions = tk.Frame(self.header, bg=V2_HEADER_BG)
        self.header_actions.pack(side="right", padx=8, pady=8)

        self.body = tk.Frame(self, bg=V2_BG)
        self.body.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self.nav = tk.Frame(self.body, bg=V2_NAV_BG, width=180)
        self.nav.pack(side="left", fill="y")
        self.nav.pack_propagate(False)

        self.workspace = tk.Frame(self.body, bg=V2_PANEL)
        self.workspace.pack(side="left", fill="both", expand=True, padx=(10, 10))

        self.inspector = tk.Frame(self.body, bg=V2_INSPECTOR_BG, width=240)
        self.inspector.pack(side="right", fill="y")
        self.inspector.pack_propagate(False)

        self.inspector_title = tk.Label(
            self.inspector,
            text="Inspector",
            bg=V2_INSPECTOR_BG,
            fg="#2b2b2b",
            font=("Cambria", 13, "bold"),
        )
        self.inspector_title.pack(anchor="w", padx=10, pady=(10, 4))

        self.inspector_text = tk.Label(
            self.inspector,
            text="Select a section to view details.",
            bg=V2_INSPECTOR_BG,
            fg="#2b2b2b",
            justify="left",
            anchor="nw",
            wraplength=220,
            font=("Calibri", 10),
        )
        self.inspector_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.status_var = tk.StringVar(value="Ready.")
        self.status_strip = tk.Label(
            self,
            textvariable=self.status_var,
            anchor="w",
            bg="#d7ccba",
            fg="#242424",
            padx=12,
            pady=6,
            font=("Calibri", 10, "bold"),
        )
        self.status_strip.pack(fill="x", padx=12, pady=(0, 12))

    def add_header_action(self, text: str, command) -> tk.Button:
        button = tk.Button(
            self.header_actions,
            text=text,
            command=command,
            bg="#d9d2c4",
            fg="#1f1f1f",
            relief="flat",
            padx=10,
            pady=6,
        )
        button.pack(side="right", padx=(8, 0))
        return button

    def add_nav_button(self, key: str, text: str, command) -> tk.Button:
        button = tk.Button(
            self.nav,
            text=text,
            command=command,
            bg=V2_NAV_BG,
            fg="#f5f5f5",
            activebackground=V2_NAV_ACTIVE,
            activeforeground="#ffffff",
            relief="flat",
            anchor="w",
            padx=14,
            pady=10,
            bd=0,
            highlightthickness=0,
        )
        button.pack(fill="x", pady=(2, 0))
        self._nav_buttons[key] = button
        return button

    def set_nav_active(self, key: str) -> None:
        for button_key, button in self._nav_buttons.items():
            if button_key == key:
                button.configure(bg=V2_NAV_ACTIVE, fg="#ffffff")
            else:
                button.configure(bg=V2_NAV_BG, fg="#f5f5f5")

    def set_status(self, text: str) -> None:
        self.status_var.set(text)

    def set_inspector(self, title: str, lines: list[str]) -> None:
        self.inspector_title.configure(text=title)
        if not lines:
            self.inspector_text.configure(text="No details.")
            return
        self.inspector_text.configure(text="\n".join(f"- {line}" for line in lines))


class HomeV2Screen(tk.Frame):
    """Feature-C home with v2 routes for authoring, runtime, and native specialist tools."""

    def __init__(self, parent: tk.Widget, app: object) -> None:
        super().__init__(parent, bg=V2_BG)
        self.app = app

        header = tk.Frame(self, bg=V2_HEADER_BG, height=68)
        header.pack(fill="x", padx=16, pady=(16, 10))
        header.pack_propagate(False)

        tk.Button(
            header,
            text="Back to Classic Home",
            command=lambda: self.app.show_screen("home"),
            bg="#d9d2c4",
            fg="#1f1f1f",
            relief="flat",
            padx=12,
            pady=6,
        ).pack(side="left", padx=(10, 10), pady=10)

        tk.Label(
            header,
            text="Home v2 - Full Visual Redesign",
            bg=V2_HEADER_BG,
            fg="#f5f5f5",
            font=("Cambria", 18, "bold"),
        ).pack(side="left", pady=10)

        tk.Label(
            self,
            text=(
                "Feature C routes through v2 pages with runtime integration and native specialist "
                "tool pages."
            ),
            bg=V2_BG,
            fg="#2a2a2a",
            anchor="w",
            justify="left",
            font=("Calibri", 11),
        ).pack(fill="x", padx=22, pady=(0, 10))

        cards = tk.Frame(self, bg=V2_BG)
        cards.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self._add_card(
            cards,
            "Schema Studio v2",
            "Authoring navigation shell with guarded transitions to schema design routes.",
            lambda: self.app.show_screen("schema_studio_v2"),
        )
        self._add_card(
            cards,
            "Run Center v2",
            "Integrated diagnostics, planning, benchmark, and multiprocess execution flow.",
            lambda: self.app.show_screen("run_center_v2"),
        )
        self._add_card(
            cards,
            "ERD Designer v2",
            "Native v2 ERD workflow with canonical schema/render/export behavior contracts.",
            lambda: self.app.show_screen("erd_designer_v2"),
        )
        self._add_card(
            cards,
            "Location Selector v2",
            "Native v2 location workflow for map selection, GeoJSON output, and deterministic samples.",
            lambda: self.app.show_screen("location_selector_v2"),
        )
        self._add_card(
            cards,
            "Generation Guide v2",
            "Native v2 read-only guide for generation configuration patterns.",
            lambda: self.app.show_screen("generation_behaviors_guide_v2"),
        )

    def _add_card(self, parent: tk.Widget, title: str, detail: str, command) -> None:
        card = tk.Frame(parent, bg=V2_PANEL, bd=1, relief="solid", highlightthickness=0)
        card.pack(fill="x", pady=(0, 10))

        tk.Label(
            card,
            text=title,
            bg=V2_PANEL,
            fg="#1b1b1b",
            font=("Cambria", 14, "bold"),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(10, 4))

        tk.Label(
            card,
            text=detail,
            bg=V2_PANEL,
            fg="#333333",
            justify="left",
            anchor="w",
            wraplength=820,
            font=("Calibri", 10),
        ).pack(fill="x", padx=14, pady=(0, 8))

        tk.Button(
            card,
            text="Open",
            command=command,
            bg=V2_NAV_ACTIVE,
            fg="#ffffff",
            relief="flat",
            padx=12,
            pady=6,
        ).pack(anchor="e", padx=14, pady=(0, 10))


class SchemaStudioV2Screen(tk.Frame):
    """Feature-C schema authoring navigation shell with dirty-state guarded routes."""

    def __init__(self, parent: tk.Widget, app: object, _cfg: AppConfig) -> None:
        super().__init__(parent, bg=V2_BG)
        self.app = app
        self.view_model = SchemaStudioViewModel()
        self.route_guard = DirtyRouteGuard()
        self.shell = V2ShellFrame(
            self,
            title="Schema Studio v2",
            on_back=lambda: self._navigate_with_guard("home_v2", "returning to Home v2"),
        )
        self.shell.pack(fill="both", expand=True)
        self.shell.add_header_action(
            "Run Center",
            lambda: self._navigate_with_guard("run_center_v2", "opening Run Center"),
        )
        self.shell.add_header_action(
            "Classic Home",
            lambda: self._navigate_with_guard("home", "returning to Classic Home"),
        )

        self.section_tabs = ttk.Notebook(self.shell.workspace)
        self.section_tabs.pack(fill="both", expand=True, padx=10, pady=10)
        self._tab_by_name: dict[str, ttk.Frame] = {}

        self._inspector_by_section = {
            "project": [
                "Project metadata and seed configuration live in schema routes.",
                "Use primary schema route for full schema editing and validation.",
                "Fallback schema routes are hidden and rollback-only in this cycle.",
            ],
            "tables": ["Open primary schema route for table authoring and SCD/business-key controls."],
            "columns": ["Open primary schema route for column generator and params authoring."],
            "relationships": ["Open primary schema route for FK relationship mapping and constraints."],
            "run": ["Use Run Center v2 for diagnostics, plan, and execution."],
        }

        self._build_tab(
            "project",
            "Project",
            lambda: self._navigate_with_guard(SCHEMA_PRIMARY_ROUTE, "opening schema project designer"),
        )
        self._build_tab(
            "tables",
            "Tables",
            lambda: self._navigate_with_guard(SCHEMA_PRIMARY_ROUTE, "opening table workflow"),
        )
        self._build_tab(
            "columns",
            "Columns",
            lambda: self._navigate_with_guard(SCHEMA_PRIMARY_ROUTE, "opening column workflow"),
        )
        self._build_tab(
            "relationships",
            "Relationships",
            lambda: self._navigate_with_guard(SCHEMA_PRIMARY_ROUTE, "opening relationship workflow"),
        )
        self._build_tab("run", "Run", lambda: self._navigate_with_guard("run_center_v2", "opening Run Center"))

        for key in ("project", "tables", "columns", "relationships", "run"):
            self.shell.add_nav_button(key, key.title(), command=lambda section_key=key: self.select_section(section_key))

        self.select_section("project")

    def _build_tab(self, key: str, title: str, command) -> None:
        frame = ttk.Frame(self.section_tabs, padding=12)
        self.section_tabs.add(frame, text=title)
        self._tab_by_name[key] = frame
        ttk.Label(
            frame,
            text=f"{title} workflow lives in the production schema routes and is fully available now.",
            justify="left",
            wraplength=640,
        ).pack(anchor="w")
        ttk.Button(frame, text=f"Open {title} workflow", command=command).pack(anchor="w", pady=(10, 0))

    def _linked_dirty_screen(self) -> object | None:
        screen = getattr(self.app, "screens", {}).get(SCHEMA_PRIMARY_ROUTE)
        if screen is not None and bool(getattr(screen, "is_dirty", False)):
            return screen
        return None

    def _navigate_with_guard(self, target_route: str, action_name: str) -> None:
        result = guarded_navigation(
            guard=self.route_guard,
            dirty_screen=self._linked_dirty_screen(),
            action_name=action_name,
            navigate=lambda: self.app.show_screen(target_route),
        )
        if not result.allowed:
            self.shell.set_status("Navigation cancelled: unsaved changes remain in schema designer.")

    def select_section(self, section_key: str) -> None:
        if section_key not in self._tab_by_name:
            return
        self.view_model.selected_section = section_key
        self.shell.set_nav_active(section_key)
        self.section_tabs.select(self._tab_by_name[section_key])
        self.shell.set_inspector(f"{section_key.title()} Inspector", self._inspector_by_section.get(section_key, []))
        self.shell.set_status(f"Schema Studio v2: viewing {section_key} section.")

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
        self.shell.add_header_action("Schema Studio", lambda: self.app.show_screen("schema_studio_v2"))
        self.shell.add_header_action("Classic Home", lambda: self.app.show_screen("home"))

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

        self._set_inspector_for_config()
        self.shell.set_status("Run Center v2 ready.")

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
        path = filedialog.askopenfilename(
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
        self._append_history("cancelled", self.surface.execution_mode_var.get(), False, 0)

    def _run_estimate(self) -> None:
        if self.lifecycle.state.is_running or not self._ensure_project():
            return
        assert self.project is not None
        model = self._sync_viewmodel_from_vars()
        try:
            diagnostics = run_shared_estimate(self.project, model)
        except ValueError as exc:
            self.error_surface.emit_exception_actionable(
                exc,
                location="Estimate workload",
                hint="review run profile values and retry",
                mode="mixed",
            )
            return
        self._clear_tree(self.diagnostics_tree)
        if self.diagnostics_tree is not None:
            for estimate in diagnostics.estimates:
                self.diagnostics_tree.insert(
                    "",
                    "end",
                    values=(
                        estimate.table_name,
                        str(estimate.estimated_rows),
                        f"{estimate.estimated_memory_mb:.3f}",
                        f"{estimate.estimated_write_mb:.3f}",
                        f"{estimate.estimated_seconds:.3f}",
                        estimate.risk_level,
                        estimate.recommendation,
                    ),
                )
        self.shell.set_status(f"Estimate complete: rows={diagnostics.summary.total_rows}, risk={diagnostics.summary.highest_risk}.")
        self._set_focus("diagnostics")

    def _run_build_plan(self) -> None:
        if self.lifecycle.state.is_running or not self._ensure_project():
            return
        assert self.project is not None
        model = self._sync_viewmodel_from_vars()
        try:
            entries = run_shared_build_partition_plan(self.project, model)
        except ValueError as exc:
            self.error_surface.emit_exception_actionable(
                exc,
                location="Build partition plan",
                hint="review execution settings and retry",
                mode="mixed",
            )
            return
        self._clear_tree(self.preview_table)
        if self.preview_table is not None:
            for entry in entries:
                self.preview_table.insert(
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
        self.shell.set_status(f"Partition plan ready: partitions={len(entries)}.")
        self._set_focus("plan")

    def _start_benchmark(self) -> None:
        if not self._ensure_project():
            return
        assert self.project is not None
        model = self._sync_viewmodel_from_vars()

        def worker() -> BenchmarkResult:
            return run_shared_benchmark(
                self.project,
                model,
                on_event=self.ui_dispatch.marshal(self._on_runtime_event),
                cancel_requested=self._is_cancel_requested,
            )

        def on_done(result: BenchmarkResult) -> None:
            self.lifecycle.transition_complete("Benchmark complete")
            self._clear_tree(self.diagnostics_tree)
            if self.diagnostics_tree is not None:
                for estimate in result.estimates:
                    self.diagnostics_tree.insert(
                        "",
                        "end",
                        values=(
                            estimate.table_name,
                            str(estimate.estimated_rows),
                            f"{estimate.estimated_memory_mb:.3f}",
                            f"{estimate.estimated_write_mb:.3f}",
                            f"{estimate.estimated_seconds:.3f}",
                            estimate.risk_level,
                            estimate.recommendation,
                        ),
                    )
            self._clear_tree(self.preview_table)
            if self.preview_table is not None:
                for entry in result.chunk_plan:
                    partition_id = f"{entry.table_name}|stage={entry.stage}|chunk={entry.chunk_index}"
                    self.preview_table.insert(
                        "",
                        "end",
                        values=(
                            entry.table_name,
                            partition_id,
                            f"{entry.start_row}-{entry.end_row}",
                            str(entry.stage),
                            "-",
                            "planned",
                        ),
                    )
            self.shell.set_status(f"Benchmark complete: chunks={result.chunk_summary.total_chunks}, rows={result.chunk_summary.total_rows}.")
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
            profile = build_profile_from_model(model)
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
            output_csv_folder = filedialog.askdirectory(title="Choose output folder for CSV export")
            if output_csv_folder in {None, ""}:
                self.shell.set_status("Run cancelled (no CSV output folder selected).")
                return
        if output_mode in {"sqlite", "all"}:
            output_sqlite_path = filedialog.asksaveasfilename(
                title="Choose SQLite output path",
                defaultextension=".db",
                filetypes=[("SQLite DB", "*.db"), ("All files", "*.*")],
                initialfile="run_center_v2.db",
            )
            if output_sqlite_path in {None, ""}:
                self.shell.set_status("Run cancelled (no SQLite output path selected).")
                return

        def worker() -> MultiprocessRunResult:
            return run_generation_multiprocess(
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
            self._clear_tree(self.preview_table)
            if self.preview_table is not None:
                for entry in result.partition_plan:
                    self.preview_table.insert(
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
            self._clear_tree(self.failures_tree)
            if self.failures_tree is not None:
                for failure in result.failures:
                    self.failures_tree.insert(
                        "",
                        "end",
                        values=(failure.partition_id, failure.error, str(failure.retry_count), failure.action),
                    )

            csv_count = len(result.strategy_result.csv_paths)
            sqlite_rows = sum(result.strategy_result.sqlite_counts.values())
            self.shell.set_status(
                f"Run complete: rows={result.total_rows}, csv_files={csv_count}, sqlite_rows={sqlite_rows}, fallback={'yes' if result.fallback_used else 'no'}."
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
        output_path = filedialog.asksaveasfilename(
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
        self.shell.set_status(f"Saved config to {output_path}.")

    def _load_profile(self) -> None:
        input_path = filedialog.askopenfilename(
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
        self.shell.set_status(f"Loaded config from {input_path}.")


class ToolBridgeV2Screen(tk.Frame):
    """Phase VR-UI-3 bridge shell that routes to an existing production screen."""

    def __init__(
        self,
        parent: tk.Widget,
        app: object,
        *,
        title: str,
        launch_label: str,
        launch_route: str,
        description: str,
        inspector_title: str,
        inspector_lines: list[str],
    ) -> None:
        super().__init__(parent, bg=V2_BG)
        self.app = app
        self.launch_route = launch_route
        self._inspector_title = inspector_title
        self._inspector_lines = inspector_lines

        self.shell = V2ShellFrame(self, title=title, on_back=lambda: self.app.show_screen("home_v2"))
        self.shell.pack(fill="both", expand=True)
        self.shell.set_status(f"{title}: bridge ready.")
        self.shell.add_header_action("Classic Home", lambda: self.app.show_screen("home"))
        self.shell.add_header_action("Home v2", lambda: self.app.show_screen("home_v2"))

        self.shell.add_nav_button("overview", "Overview", command=self._show_overview)
        self.shell.add_nav_button("open", "Open Current Tool", command=self._open_current)

        self.body_card = tk.Frame(self.shell.workspace, bg=V2_PANEL, bd=1, relief="solid")
        self.body_card.pack(fill="x", padx=12, pady=12)
        tk.Label(self.body_card, text=description, bg=V2_PANEL, fg="#333333", anchor="w", justify="left", wraplength=760, font=("Calibri", 10)).pack(fill="x", padx=12, pady=(12, 10))

        self.launch_btn = tk.Button(self.body_card, text=launch_label, command=self._open_current, bg=V2_NAV_ACTIVE, fg="#ffffff", relief="flat", padx=12, pady=6)
        self.launch_btn.pack(anchor="e", padx=12, pady=(0, 12))

        self._show_overview()

    def _show_overview(self) -> None:
        self.shell.set_nav_active("overview")
        self.shell.set_inspector(self._inspector_title, self._inspector_lines)
        self.shell.set_status("Bridge overview ready.")

    def _open_current(self) -> None:
        self.shell.set_nav_active("open")
        self.shell.set_status(f"Opening production route '{self.launch_route}'.")
        self.app.show_screen(self.launch_route)


class ERDDesignerV2Screen(tk.Frame):
    """Native v2 route for ERD designer behavior."""

    def __init__(self, parent: tk.Widget, app: object, cfg: AppConfig) -> None:
        super().__init__(parent, bg=V2_BG)
        self.app = app
        self.view_model = ERDDesignerV2ViewModel()
        self.shell = V2ShellFrame(self, title="ERD Designer v2", on_back=lambda: self.app.show_screen("home_v2"))
        self.shell.pack(fill="both", expand=True)
        self.shell.add_header_action("Classic Home", lambda: self.app.show_screen("home"))
        self.shell.add_header_action("Home v2", lambda: self.app.show_screen("home_v2"))
        self.shell.add_nav_button("tool", "ERD Tool", command=self._show_tool)
        self.shell.add_nav_button("overview", "Overview", command=self._show_overview)

        self.tool = ERDDesignerToolFrame(
            self.shell.workspace,
            _BackToRouteAdapter(lambda: self.app.show_screen("home_v2")),
            cfg,
            show_header=False,
            title_text="ERD Designer v2",
        )
        self.tool.pack(fill="both", expand=True, padx=8, pady=8)
        self._show_tool()

    def _show_tool(self) -> None:
        self.view_model.selected_section = "erd"
        self.shell.set_nav_active("tool")
        self.shell.set_inspector(
            "ERD Inspector",
            [
                "Native v2 page uses canonical ERD authoring/render/export contracts.",
                "Schema render, drag layout, and export behavior remain deterministic.",
            ],
        )
        self.shell.set_status("ERD Designer v2 ready.")

    def _show_overview(self) -> None:
        self.shell.set_nav_active("overview")
        self.shell.set_inspector(
            "ERD Overview",
            [
                "Use this page to load or author schema tables/columns/FKs and render ERD.",
                "Exports support SVG/PNG/JPEG with actionable validation feedback.",
            ],
        )
        self.shell.set_status("ERD Designer v2 overview.")


class LocationSelectorV2Screen(tk.Frame):
    """Native v2 route for location selector behavior."""

    def __init__(self, parent: tk.Widget, app: object, cfg: AppConfig) -> None:
        super().__init__(parent, bg=V2_BG)
        self.app = app
        self.view_model = LocationSelectorV2ViewModel()
        self.shell = V2ShellFrame(self, title="Location Selector v2", on_back=lambda: self.app.show_screen("home_v2"))
        self.shell.pack(fill="both", expand=True)
        self.shell.add_header_action("Classic Home", lambda: self.app.show_screen("home"))
        self.shell.add_header_action("Home v2", lambda: self.app.show_screen("home_v2"))
        self.shell.add_nav_button("tool", "Location Tool", command=self._show_tool)
        self.shell.add_nav_button("overview", "Overview", command=self._show_overview)

        self.tool = LocationSelectorToolFrame(
            self.shell.workspace,
            _BackToRouteAdapter(lambda: self.app.show_screen("home_v2")),
            cfg,
            show_header=False,
            title_text="Location Selector v2",
        )
        self.tool.pack(fill="both", expand=True, padx=8, pady=8)
        self._show_tool()

    def _show_tool(self) -> None:
        self.view_model.selected_section = "location"
        self.shell.set_nav_active("tool")
        self.shell.set_inspector(
            "Location Inspector",
            [
                "Native v2 page uses canonical map/GeoJSON/sample contracts.",
                "Sample output remains deterministic for seed + inputs.",
            ],
        )
        self.shell.set_status("Location Selector v2 ready.")

    def _show_overview(self) -> None:
        self.shell.set_nav_active("overview")
        self.shell.set_inspector(
            "Location Overview",
            [
                "Select a center point and radius to build GeoJSON output.",
                "Generate and save deterministic latitude/longitude sample points.",
            ],
        )
        self.shell.set_status("Location Selector v2 overview.")


class GenerationBehaviorsGuideV2Screen(tk.Frame):
    """Native v2 route for generation guide behavior."""

    def __init__(self, parent: tk.Widget, app: object, _cfg: AppConfig) -> None:
        super().__init__(parent, bg=V2_BG)
        self.app = app
        self.view_model = GenerationGuideV2ViewModel()
        self.shell = V2ShellFrame(self, title="Generation Guide v2", on_back=lambda: self.app.show_screen("home_v2"))
        self.shell.pack(fill="both", expand=True)
        self.shell.add_header_action("Classic Home", lambda: self.app.show_screen("home"))
        self.shell.add_header_action("Home v2", lambda: self.app.show_screen("home_v2"))
        self.shell.add_nav_button("guide", "Guide", command=self._show_guide)
        self.shell.add_nav_button("overview", "Overview", command=self._show_overview)

        self.tool = GenerationGuideToolFrame(
            self.shell.workspace,
            _BackToRouteAdapter(lambda: self.app.show_screen("home_v2")),
            show_header=False,
            title_text="Generation Guide v2",
        )
        self.tool.pack(fill="both", expand=True, padx=8, pady=8)
        self._show_guide()

    def _show_guide(self) -> None:
        self.view_model.selected_section = "guide"
        self.shell.set_nav_active("guide")
        self.shell.set_inspector(
            "Guide Inspector",
            [
                "Read-only generation behavior reference for schema authoring.",
                "No schema mutation controls are exposed on this route.",
            ],
        )
        self.shell.set_status("Generation Guide v2 ready.")

    def _show_overview(self) -> None:
        self.shell.set_nav_active("overview")
        self.shell.set_inspector(
            "Guide Overview",
            [
                "Covers dtype defaults, generator params, dependency flows, and SCD/BK guidance.",
                "Behavior definitions remain aligned with canonical semantics docs.",
            ],
        )
        self.shell.set_status("Generation Guide v2 overview.")


class ERDDesignerV2BridgeScreen(ToolBridgeV2Screen):
    """Hidden fallback bridge route for ERD designer."""

    def __init__(self, parent: tk.Widget, app: object, _cfg: AppConfig) -> None:
        super().__init__(
            parent,
            app,
            title="ERD Designer v2 Bridge",
            launch_label="Open current ERD Designer",
            launch_route="erd_designer",
            description="Fallback bridge route to the production ERD designer.",
            inspector_title="ERD Bridge Notes",
            inspector_lines=[
                "This route is retained temporarily for rollback safety.",
                "Primary v2 ERD behavior now lives on erd_designer_v2.",
            ],
        )


class LocationSelectorV2BridgeScreen(ToolBridgeV2Screen):
    """Hidden fallback bridge route for location selector."""

    def __init__(self, parent: tk.Widget, app: object, _cfg: AppConfig) -> None:
        super().__init__(
            parent,
            app,
            title="Location Selector v2 Bridge",
            launch_label="Open current Location Selector",
            launch_route="location_selector",
            description="Fallback bridge route to the production location selector.",
            inspector_title="Location Bridge Notes",
            inspector_lines=[
                "This route is retained temporarily for rollback safety.",
                "Primary v2 location behavior now lives on location_selector_v2.",
            ],
        )


class GenerationBehaviorsGuideV2BridgeScreen(ToolBridgeV2Screen):
    """Hidden fallback bridge route for generation guide."""

    def __init__(self, parent: tk.Widget, app: object, _cfg: AppConfig) -> None:
        super().__init__(
            parent,
            app,
            title="Generation Guide v2 Bridge",
            launch_label="Open current Generation Behaviors Guide",
            launch_route="generation_behaviors_guide",
            description="Fallback bridge route to the production generation guide.",
            inspector_title="Guide Bridge Notes",
            inspector_lines=[
                "This route is retained temporarily for rollback safety.",
                "Primary v2 guide behavior now lives on generation_behaviors_guide_v2.",
            ],
        )

