from __future__ import annotations

import json
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from src.config import AppConfig
from src.gui_v2.commands import run_benchmark
from src.gui_v2.commands import run_build_partition_plan
from src.gui_v2.commands import run_estimate
from src.gui_v2.commands import run_generation
from src.gui_v2.navigation import DirtyRouteGuard
from src.gui_v2.navigation import guarded_navigation
from src.gui_v2.viewmodels import RunCenterViewModel
from src.gui_v2.viewmodels import SchemaStudioViewModel
from src.gui_v2.viewmodels import coerce_execution_mode
from src.gui_v2.viewmodels import coerce_output_mode
from src.multiprocessing_runtime import EXECUTION_MODES
from src.multiprocessing_runtime import MultiprocessEvent
from src.multiprocessing_runtime import MultiprocessRunCancelled
from src.multiprocessing_runtime import MultiprocessRunResult
from src.performance_scaling import FK_CACHE_MODES
from src.performance_scaling import OUTPUT_MODES
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
    """Feature-C home with v2 routes for authoring, runtime, and parity bridges."""

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
                "Feature C is routed through v2 pages with runtime integration and parity bridges "
                "for specialist tools."
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
            "ERD Designer v2 Bridge",
            "V2 parity bridge layout that launches the current ERD designer route.",
            lambda: self.app.show_screen("erd_designer_v2"),
        )
        self._add_card(
            cards,
            "Location Selector v2 Bridge",
            "V2 parity bridge layout that launches the current location selector route.",
            lambda: self.app.show_screen("location_selector_v2"),
        )
        self._add_card(
            cards,
            "Generation Guide v2 Bridge",
            "V2 parity bridge layout that launches the current behavior guide route.",
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
                "Use production route for full schema editing and validation.",
                "Navigation from v2 applies dirty-state guard when possible.",
            ],
            "tables": ["Open schema routes for table authoring and SCD/business-key controls."],
            "columns": ["Open schema routes for column generator and params authoring."],
            "relationships": ["Open schema routes for FK relationship mapping and constraints."],
            "run": ["Use Run Center v2 for diagnostics, plan, and execution."],
        }

        self._build_tab("project", "Project", lambda: self._navigate_with_guard("schema_project", "opening schema project designer"))
        self._build_tab("tables", "Tables", lambda: self._navigate_with_guard("schema_project_kit", "opening schema kit route"))
        self._build_tab("columns", "Columns", lambda: self._navigate_with_guard("schema_project", "opening column workflow"))
        self._build_tab("relationships", "Relationships", lambda: self._navigate_with_guard("schema_project", "opening relationship workflow"))
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
        for route in ("schema_project", "schema_project_kit", "schema_project_legacy"):
            screen = getattr(self.app, "screens", {}).get(route)
            if screen is None:
                continue
            if bool(getattr(screen, "is_dirty", False)):
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
        self._is_running = False
        self._cancel_requested = False
        self._run_started_at = 0.0

        self.view_model = RunCenterViewModel()
        self.schema_path_var = tk.StringVar(value="")
        self.target_tables_var = tk.StringVar(value="")
        self.row_overrides_var = tk.StringVar(value="")
        self.preview_row_target_var = tk.StringVar(value="500")
        self.output_mode_var = tk.StringVar(value=OUTPUT_MODES[0])
        self.chunk_size_rows_var = tk.StringVar(value="10000")
        self.preview_page_size_var = tk.StringVar(value="500")
        self.sqlite_batch_size_var = tk.StringVar(value="5000")
        self.csv_buffer_rows_var = tk.StringVar(value="5000")
        self.fk_cache_mode_var = tk.StringVar(value=FK_CACHE_MODES[0])
        self.strict_chunking_var = tk.BooleanVar(value=True)
        self.execution_mode_var = tk.StringVar(value=EXECUTION_MODES[0])
        self.worker_count_var = tk.StringVar(value="1")
        self.max_inflight_chunks_var = tk.StringVar(value="4")
        self.ipc_queue_size_var = tk.StringVar(value="128")
        self.retry_limit_var = tk.StringVar(value="1")
        self.profile_name_var = tk.StringVar(value="default_v2_profile")

        self.live_phase_var = tk.StringVar(value="Idle")
        self.live_rows_var = tk.StringVar(value="Rows processed: 0")
        self.live_eta_var = tk.StringVar(value="ETA: --")

        self.shell = V2ShellFrame(self, title="Run Center v2", on_back=lambda: self.app.show_screen("home_v2"))
        self.shell.pack(fill="both", expand=True)
        self.shell.add_header_action("Schema Studio", lambda: self.app.show_screen("schema_studio_v2"))
        self.shell.add_header_action("Classic Home", lambda: self.app.show_screen("home"))
        self.shell.set_status("Run Center v2 ready.")

        self.shell.add_nav_button("config", "Run Config", lambda: self._set_focus("config"))
        self.shell.add_nav_button("diagnostics", "Diagnostics", lambda: self._set_focus("diagnostics"))
        self.shell.add_nav_button("plan", "Plan", lambda: self._set_focus("plan"))
        self.shell.add_nav_button("failures", "Failures", lambda: self._set_focus("failures"))
        self.shell.add_nav_button("history", "History", lambda: self._set_focus("history"))
        self.shell.set_nav_active("config")

        self._build_config_card()
        self.progress = ttk.Progressbar(self.shell.workspace, mode="determinate", maximum=100.0, value=0.0)
        self.progress.pack(fill="x", padx=10, pady=(0, 4))

        live = ttk.Frame(self.shell.workspace)
        live.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Label(live, textvariable=self.live_phase_var).pack(side="left", padx=(0, 12))
        ttk.Label(live, textvariable=self.live_rows_var).pack(side="left", padx=(0, 12))
        ttk.Label(live, textvariable=self.live_eta_var).pack(side="left")

        self._build_results_workspace()
        self._set_inspector_for_config()

    def _build_config_card(self) -> None:
        self.config_card = ttk.LabelFrame(self.shell.workspace, text="Run Config", padding=10)
        self.config_card.pack(fill="x", padx=10, pady=(10, 6))
        for idx in (1, 3):
            self.config_card.columnconfigure(idx, weight=1)

        ttk.Label(self.config_card, text="Schema JSON").grid(row=0, column=0, sticky="w")
        ttk.Entry(self.config_card, textvariable=self.schema_path_var).grid(row=0, column=1, columnspan=3, sticky="ew", padx=(8, 8))
        ttk.Button(self.config_card, text="Browse...", command=self._browse_schema_path).grid(row=0, column=4, sticky="ew", padx=(0, 8))
        ttk.Button(self.config_card, text="Load", command=self._load_schema).grid(row=0, column=5, sticky="ew")

        ttk.Label(self.config_card, text="Target tables").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(self.config_card, textvariable=self.target_tables_var).grid(row=1, column=1, sticky="ew", padx=(8, 20), pady=(6, 0))
        ttk.Label(self.config_card, text="Row overrides JSON").grid(row=1, column=2, sticky="w", pady=(6, 0))
        ttk.Entry(self.config_card, textvariable=self.row_overrides_var).grid(row=1, column=3, columnspan=3, sticky="ew", padx=(8, 0), pady=(6, 0))

        ttk.Label(self.config_card, text="Output").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(self.config_card, textvariable=self.output_mode_var, state="readonly", values=OUTPUT_MODES, width=12).grid(row=2, column=1, sticky="w", padx=(8, 20), pady=(6, 0))
        ttk.Label(self.config_card, text="Execution mode").grid(row=2, column=2, sticky="w", pady=(6, 0))
        ttk.Combobox(self.config_card, textvariable=self.execution_mode_var, state="readonly", values=EXECUTION_MODES, width=20).grid(row=2, column=3, sticky="w", padx=(8, 20), pady=(6, 0))
        ttk.Label(self.config_card, text="Profile").grid(row=2, column=4, sticky="w", pady=(6, 0))
        ttk.Entry(self.config_card, textvariable=self.profile_name_var, width=16).grid(row=2, column=5, sticky="w", pady=(6, 0))

        ttk.Label(self.config_card, text="Chunk").grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(self.config_card, textvariable=self.chunk_size_rows_var, width=10).grid(row=3, column=1, sticky="w", padx=(8, 20), pady=(6, 0))
        ttk.Label(self.config_card, text="Workers").grid(row=3, column=2, sticky="w", pady=(6, 0))
        ttk.Entry(self.config_card, textvariable=self.worker_count_var, width=10).grid(row=3, column=3, sticky="w", padx=(8, 20), pady=(6, 0))
        ttk.Label(self.config_card, text="Inflight").grid(row=3, column=4, sticky="w", pady=(6, 0))
        ttk.Entry(self.config_card, textvariable=self.max_inflight_chunks_var, width=10).grid(row=3, column=5, sticky="w", pady=(6, 0))

        ttk.Label(self.config_card, text="Preview target").grid(row=4, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(self.config_card, textvariable=self.preview_row_target_var, width=10).grid(row=4, column=1, sticky="w", padx=(8, 20), pady=(6, 0))
        ttk.Label(self.config_card, text="Page size").grid(row=4, column=2, sticky="w", pady=(6, 0))
        ttk.Entry(self.config_card, textvariable=self.preview_page_size_var, width=10).grid(row=4, column=3, sticky="w", padx=(8, 20), pady=(6, 0))
        ttk.Label(self.config_card, text="SQLite batch").grid(row=4, column=4, sticky="w", pady=(6, 0))
        ttk.Entry(self.config_card, textvariable=self.sqlite_batch_size_var, width=10).grid(row=4, column=5, sticky="w", pady=(6, 0))

        ttk.Label(self.config_card, text="CSV buffer").grid(row=5, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(self.config_card, textvariable=self.csv_buffer_rows_var, width=10).grid(row=5, column=1, sticky="w", padx=(8, 20), pady=(6, 0))
        ttk.Label(self.config_card, text="FK cache").grid(row=5, column=2, sticky="w", pady=(6, 0))
        ttk.Combobox(self.config_card, textvariable=self.fk_cache_mode_var, state="readonly", values=FK_CACHE_MODES, width=12).grid(row=5, column=3, sticky="w", padx=(8, 20), pady=(6, 0))
        ttk.Label(self.config_card, text="Retry").grid(row=5, column=4, sticky="w", pady=(6, 0))
        ttk.Entry(self.config_card, textvariable=self.retry_limit_var, width=10).grid(row=5, column=5, sticky="w", pady=(6, 0))

        ttk.Label(self.config_card, text="IPC queue").grid(row=6, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(self.config_card, textvariable=self.ipc_queue_size_var, width=10).grid(row=6, column=1, sticky="w", padx=(8, 20), pady=(6, 0))
        ttk.Checkbutton(self.config_card, text="Strict deterministic chunking", variable=self.strict_chunking_var).grid(row=6, column=2, columnspan=3, sticky="w", pady=(6, 0))

        actions = ttk.Frame(self.config_card)
        actions.grid(row=7, column=0, columnspan=6, sticky="ew", pady=(10, 0))
        for idx in range(8):
            actions.columnconfigure(idx, weight=1)

        self.estimate_btn = ttk.Button(actions, text="Estimate", command=self._run_estimate)
        self.estimate_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.build_plan_btn = ttk.Button(actions, text="Build plan", command=self._run_build_plan)
        self.build_plan_btn.grid(row=0, column=1, sticky="ew", padx=4)
        self.run_benchmark_btn = ttk.Button(actions, text="Benchmark", command=self._start_benchmark)
        self.run_benchmark_btn.grid(row=0, column=2, sticky="ew", padx=4)
        self.start_run_btn = ttk.Button(actions, text="Start", command=self._start_generation)
        self.start_run_btn.grid(row=0, column=3, sticky="ew", padx=4)
        self.start_fallback_btn = ttk.Button(actions, text="Start + Fallback", command=lambda: self._start_generation(fallback_to_single_process=True))
        self.start_fallback_btn.grid(row=0, column=4, sticky="ew", padx=4)
        self.cancel_run_btn = ttk.Button(actions, text="Cancel", command=self._cancel_run, state=tk.DISABLED)
        self.cancel_run_btn.grid(row=0, column=5, sticky="ew", padx=4)
        ttk.Button(actions, text="Save config", command=self._save_profile).grid(row=0, column=6, sticky="ew", padx=4)
        ttk.Button(actions, text="Load config", command=self._load_profile).grid(row=0, column=7, sticky="ew", padx=(4, 0))

    def _build_results_workspace(self) -> None:
        self.results_tabs = ttk.Notebook(self.shell.workspace)
        self.results_tabs.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        diagnostics_tab = ttk.Frame(self.results_tabs, padding=8)
        plan_tab = ttk.Frame(self.results_tabs, padding=8)
        failures_tab = ttk.Frame(self.results_tabs, padding=8)
        history_tab = ttk.Frame(self.results_tabs, padding=8)
        self.results_tabs.add(diagnostics_tab, text="Diagnostics")
        self.results_tabs.add(plan_tab, text="Plan")
        self.results_tabs.add(failures_tab, text="Failures")
        self.results_tabs.add(history_tab, text="History")

        for tab in (diagnostics_tab, plan_tab, failures_tab, history_tab):
            tab.columnconfigure(0, weight=1)
            tab.rowconfigure(0, weight=1)

        self.diagnostics_tree = ttk.Treeview(diagnostics_tab, columns=("table", "rows", "memory", "write", "time", "risk", "recommendation"), show="headings", height=8)
        self.diagnostics_tree.grid(row=0, column=0, sticky="nsew")
        for column, text, width in (("table", "Table", 140), ("rows", "Rows", 90), ("memory", "Memory", 90), ("write", "Write", 90), ("time", "Time", 80), ("risk", "Risk", 70), ("recommendation", "Recommendation", 360)):
            self.diagnostics_tree.heading(column, text=text, anchor="w")
            self.diagnostics_tree.column(column, width=width, anchor="w")

        self.preview_table = ttk.Treeview(plan_tab, columns=("table", "partition", "row_range", "stage", "worker", "status"), show="headings", height=8)
        self.preview_table.grid(row=0, column=0, sticky="nsew")
        for column, text, width in (("table", "Table", 120), ("partition", "Partition", 260), ("row_range", "Row range", 120), ("stage", "Stage", 70), ("worker", "Worker", 80), ("status", "Status", 90)):
            self.preview_table.heading(column, text=text, anchor="w")
            self.preview_table.column(column, width=width, anchor="w")

        self.failures_tree = ttk.Treeview(failures_tab, columns=("partition", "error", "retry", "action"), show="headings", height=8)
        self.failures_tree.grid(row=0, column=0, sticky="nsew")
        for column, text, width in (("partition", "Partition", 240), ("error", "Error", 430), ("retry", "Retry", 80), ("action", "Action", 100)):
            self.failures_tree.heading(column, text=text, anchor="w")
            self.failures_tree.column(column, width=width, anchor="w")

        self.history_tree = ttk.Treeview(history_tab, columns=("timestamp", "status", "mode", "fallback", "rows"), show="headings", height=8)
        self.history_tree.grid(row=0, column=0, sticky="nsew")
        for column, text, width in (("timestamp", "Timestamp", 170), ("status", "Status", 170), ("mode", "Mode", 150), ("fallback", "Fallback", 90), ("rows", "Rows", 100)):
            self.history_tree.heading(column, text=text, anchor="w")
            self.history_tree.column(column, width=width, anchor="w")

    def _set_inspector_for_config(self) -> None:
        self.shell.set_inspector("Run Center Notes", [
            "Run Center v2 is wired to performance + multiprocessing runtimes.",
            "Estimate/plan/benchmark/start preserve canonical validation and deterministic semantics.",
            "Errors preserve location + fix hints.",
        ])

    def _set_focus(self, key: str) -> None:
        self.shell.set_nav_active(key)
        if key == "diagnostics":
            self.results_tabs.select(0)
        elif key == "plan":
            self.results_tabs.select(1)
        elif key == "failures":
            self.results_tabs.select(2)
        elif key == "history":
            self.results_tabs.select(3)
        self.shell.set_status(f"Run Center v2: focus set to {key}.")

    def _sync_viewmodel_from_vars(self) -> None:
        self.view_model.schema_path = self.schema_path_var.get().strip()
        self.view_model.target_tables = self.target_tables_var.get().strip()
        self.view_model.row_overrides_json = self.row_overrides_var.get().strip()
        self.view_model.preview_row_target = self.preview_row_target_var.get().strip()
        self.view_model.output_mode = coerce_output_mode(self.output_mode_var.get())
        self.view_model.chunk_size_rows = self.chunk_size_rows_var.get().strip()
        self.view_model.preview_page_size = self.preview_page_size_var.get().strip()
        self.view_model.sqlite_batch_size = self.sqlite_batch_size_var.get().strip()
        self.view_model.csv_buffer_rows = self.csv_buffer_rows_var.get().strip()
        self.view_model.fk_cache_mode = self.fk_cache_mode_var.get().strip()
        self.view_model.strict_deterministic_chunking = bool(self.strict_chunking_var.get())
        self.view_model.execution_mode = coerce_execution_mode(self.execution_mode_var.get())
        self.view_model.worker_count = self.worker_count_var.get().strip()
        self.view_model.max_inflight_chunks = self.max_inflight_chunks_var.get().strip()
        self.view_model.ipc_queue_size = self.ipc_queue_size_var.get().strip()
        self.view_model.retry_limit = self.retry_limit_var.get().strip()
        self.view_model.profile_name = self.profile_name_var.get().strip() or "default_v2_profile"

    def _browse_schema_path(self) -> None:
        path = filedialog.askopenfilename(title="Select schema project JSON", filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if path:
            self.schema_path_var.set(path)

    def _load_schema(self) -> bool:
        self._sync_viewmodel_from_vars()
        path = self.view_model.schema_path
        if path == "":
            messagebox.showerror("Run Center v2 error", _v2_error("Schema path", "path is required", "choose an existing schema project JSON file"))
            return False
        try:
            loaded = load_project_from_json(path)
        except (ValueError, OSError) as exc:
            messagebox.showerror("Run Center v2 error", str(exc))
            return False
        self.project = loaded
        self._loaded_schema_path = path
        self.shell.set_status(f"Loaded schema '{loaded.name}' with {len(loaded.tables)} tables.")
        return True

    def _ensure_project(self) -> bool:
        self._sync_viewmodel_from_vars()
        path_now = self.view_model.schema_path
        if self.project is None:
            return self._load_schema()
        if path_now == "":
            return True
        if path_now != self._loaded_schema_path:
            return self._load_schema()
        return True

    def _clear_tree(self, tree: ttk.Treeview) -> None:
        for item in tree.get_children():
            tree.delete(item)

    def _set_running(self, running: bool, phase: str) -> None:
        self._is_running = running
        self.live_phase_var.set(phase)
        if running:
            self._run_started_at = time.monotonic()
            self._cancel_requested = False
            self.cancel_run_btn.configure(state=tk.NORMAL)
            for button in (self.estimate_btn, self.build_plan_btn, self.run_benchmark_btn, self.start_run_btn, self.start_fallback_btn):
                button.configure(state=tk.DISABLED)
        else:
            self.cancel_run_btn.configure(state=tk.DISABLED)
            for button in (self.estimate_btn, self.build_plan_btn, self.run_benchmark_btn, self.start_run_btn, self.start_fallback_btn):
                button.configure(state=tk.NORMAL)

    def _cancel_run(self) -> None:
        if not self._is_running:
            return
        self._cancel_requested = True
        self.live_phase_var.set("Cancelling...")
        self.shell.set_status("Cancellation requested. Waiting for current step to stop...")

    def _is_cancel_requested(self) -> bool:
        return self._cancel_requested

    def _append_history(self, status: str, mode: str, fallback: bool, rows: int) -> None:
        self.history_tree.insert("", 0, values=(time.strftime("%Y-%m-%d %H:%M:%S"), status, mode, "yes" if fallback else "no", str(rows)))

    def _on_runtime_event(self, event: RuntimeEvent) -> None:
        if event.kind == "started":
            self.progress.configure(value=0.0)
            self.live_phase_var.set(event.message or "Benchmark started.")
            self.live_rows_var.set(f"Rows processed: 0/{event.total_rows}")
            self.live_eta_var.set("ETA: calculating...")
            return
        if event.kind in {"progress", "table_done"}:
            total_rows = max(1, event.total_rows)
            processed = max(0, event.rows_processed)
            percent = min(100.0, (float(processed) / float(total_rows)) * 100.0)
            self.progress.configure(value=percent)
            self.live_phase_var.set(event.message or "Benchmark running...")
            self.live_rows_var.set(f"Rows processed: {processed}/{event.total_rows}")
            return
        if event.kind == "run_done":
            self.progress.configure(value=100.0)
            self.live_phase_var.set(event.message or "Benchmark complete.")
            self.live_rows_var.set(f"Rows processed: {event.rows_processed}/{event.total_rows}")

    def _on_multiprocess_event(self, event: MultiprocessEvent) -> None:
        if event.kind == "started":
            self.progress.configure(value=0.0)
            self.live_phase_var.set(event.message or "Run started.")
            self.live_rows_var.set(f"Rows processed: 0/{event.total_rows}")
            self.live_eta_var.set("ETA: calculating...")
            return
        if event.kind == "progress":
            total_rows = max(1, event.total_rows)
            processed = max(0, event.rows_processed)
            percent = min(100.0, (float(processed) / float(total_rows)) * 100.0)
            self.progress.configure(value=percent)
            self.live_phase_var.set(event.message or "Run progress.")
            self.live_rows_var.set(f"Rows processed: {processed}/{event.total_rows}")
            return
        if event.kind == "partition_failed":
            if event.partition_id:
                self.failures_tree.insert("", "end", values=(event.partition_id, event.message, str(event.retry_count), "retry"))
            return
        if event.kind == "fallback":
            self.live_phase_var.set(event.message or "Fallback mode.")
            self.live_eta_var.set("ETA: fallback")
            return
        if event.kind == "run_done":
            self.progress.configure(value=100.0)
            self.live_phase_var.set(event.message or "Run complete.")
            self.live_rows_var.set(f"Rows processed: {event.rows_processed}/{event.total_rows}")

    def _run_async(self, *, phase_label: str, worker, on_done) -> None:
        if self._is_running:
            return
        self._set_running(True, phase_label)

        def work() -> None:
            try:
                result = worker()
            except (PerformanceRunCancelled, MultiprocessRunCancelled) as exc:
                self.after(0, lambda message=str(exc): self._on_run_cancelled(message))
                return
            except ValueError as exc:
                self.after(0, lambda message=str(exc): self._on_run_failed(message))
                return
            except Exception as exc:
                self.after(0, lambda message=str(exc): self._on_run_failed(message))
                return
            self.after(0, lambda payload=result: on_done(payload))

        threading.Thread(target=work, daemon=True).start()

    def _on_run_failed(self, message: str) -> None:
        self._set_running(False, "Failed")
        self.shell.set_status(message)
        messagebox.showerror("Run Center v2 error", message)
        self._append_history("failed", self.execution_mode_var.get(), False, 0)

    def _on_run_cancelled(self, message: str) -> None:
        self._set_running(False, "Cancelled")
        self.live_phase_var.set("Run cancelled.")
        self.live_eta_var.set("ETA: cancelled")
        self.shell.set_status(message)
        self._append_history("cancelled", self.execution_mode_var.get(), False, 0)

    def _run_estimate(self) -> None:
        if self._is_running or not self._ensure_project():
            return
        assert self.project is not None
        self._sync_viewmodel_from_vars()
        try:
            diagnostics = run_estimate(self.project, self.view_model)
        except ValueError as exc:
            messagebox.showerror("Run Center v2 error", str(exc))
            return
        self._clear_tree(self.diagnostics_tree)
        for estimate in diagnostics.estimates:
            self.diagnostics_tree.insert("", "end", values=(estimate.table_name, str(estimate.estimated_rows), f"{estimate.estimated_memory_mb:.3f}", f"{estimate.estimated_write_mb:.3f}", f"{estimate.estimated_seconds:.3f}", estimate.risk_level, estimate.recommendation))
        self.shell.set_status(f"Estimate complete: rows={diagnostics.summary.total_rows}, risk={diagnostics.summary.highest_risk}.")
        self._set_focus("diagnostics")

    def _run_build_plan(self) -> None:
        if self._is_running or not self._ensure_project():
            return
        assert self.project is not None
        self._sync_viewmodel_from_vars()
        try:
            entries = run_build_partition_plan(self.project, self.view_model)
        except ValueError as exc:
            messagebox.showerror("Run Center v2 error", str(exc))
            return
        self._clear_tree(self.preview_table)
        for entry in entries:
            self.preview_table.insert("", "end", values=(entry.table_name, entry.partition_id, f"{entry.start_row}-{entry.end_row}", str(entry.stage), str(entry.assigned_worker), entry.status))
        self.shell.set_status(f"Partition plan ready: partitions={len(entries)}.")
        self._set_focus("plan")

    def _start_benchmark(self) -> None:
        if not self._ensure_project():
            return
        assert self.project is not None
        self._sync_viewmodel_from_vars()

        def worker():
            return run_benchmark(
                self.project,
                self.view_model,
                on_event=lambda event: self.after(0, lambda evt=event: self._on_runtime_event(evt)),
                cancel_requested=self._is_cancel_requested,
            )

        def on_done(result: BenchmarkResult) -> None:
            self._set_running(False, "Benchmark complete")
            self._clear_tree(self.diagnostics_tree)
            for estimate in result.estimates:
                self.diagnostics_tree.insert("", "end", values=(estimate.table_name, str(estimate.estimated_rows), f"{estimate.estimated_memory_mb:.3f}", f"{estimate.estimated_write_mb:.3f}", f"{estimate.estimated_seconds:.3f}", estimate.risk_level, estimate.recommendation))
            self._clear_tree(self.preview_table)
            for entry in result.chunk_plan:
                part = f"{entry.table_name}|stage={entry.stage}|chunk={entry.chunk_index}"
                self.preview_table.insert("", "end", values=(entry.table_name, part, f"{entry.start_row}-{entry.end_row}", str(entry.stage), "-", "planned"))
            self.shell.set_status(f"Benchmark complete: chunks={result.chunk_summary.total_chunks}, rows={result.chunk_summary.total_rows}.")
            self._append_history("benchmark_complete", self.execution_mode_var.get(), False, result.chunk_summary.total_rows)

        self._run_async(phase_label="Running benchmark...", worker=worker, on_done=on_done)

    def _start_generation(self, fallback_to_single_process: bool = False) -> None:
        if not self._ensure_project():
            return
        assert self.project is not None
        self._sync_viewmodel_from_vars()

        output_mode = self.view_model.output_mode
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

        def worker():
            return run_generation(
                self.project,
                self.view_model,
                output_csv_folder=output_csv_folder,
                output_sqlite_path=output_sqlite_path,
                on_event=lambda event: self.after(0, lambda evt=event: self._on_multiprocess_event(evt)),
                cancel_requested=self._is_cancel_requested,
                fallback_to_single_process=fallback_to_single_process,
            )

        def on_done(result: MultiprocessRunResult) -> None:
            self._set_running(False, "Run complete")
            self._clear_tree(self.preview_table)
            for entry in result.partition_plan:
                self.preview_table.insert("", "end", values=(entry.table_name, entry.partition_id, f"{entry.start_row}-{entry.end_row}", str(entry.stage), str(entry.assigned_worker), entry.status))
            self._clear_tree(self.failures_tree)
            for failure in result.failures:
                self.failures_tree.insert("", "end", values=(failure.partition_id, failure.error, str(failure.retry_count), failure.action))

            csv_count = len(result.strategy_result.csv_paths)
            sqlite_rows = sum(result.strategy_result.sqlite_counts.values())
            self.shell.set_status(
                f"Run complete: rows={result.total_rows}, csv_files={csv_count}, sqlite_rows={sqlite_rows}, fallback={'yes' if result.fallback_used else 'no'}."
            )
            self._append_history("run_complete", result.mode, result.fallback_used, result.total_rows)

        label = "Running with fallback..." if fallback_to_single_process else "Running..."
        self._run_async(phase_label=label, worker=worker, on_done=on_done)

    def _save_profile(self) -> None:
        self._sync_viewmodel_from_vars()
        output_path = filedialog.asksaveasfilename(
            title="Save Run Center v2 config JSON",
            defaultextension=".json",
            initialfile=f"{self.view_model.profile_name}.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if output_path == "":
            self.shell.set_status("Save config cancelled.")
            return
        payload = {
            "schema_path": self.view_model.schema_path,
            "target_tables": self.view_model.target_tables,
            "row_overrides_json": self.view_model.row_overrides_json,
            "preview_row_target": self.view_model.preview_row_target,
            "output_mode": self.view_model.output_mode,
            "chunk_size_rows": self.view_model.chunk_size_rows,
            "preview_page_size": self.view_model.preview_page_size,
            "sqlite_batch_size": self.view_model.sqlite_batch_size,
            "csv_buffer_rows": self.view_model.csv_buffer_rows,
            "fk_cache_mode": self.view_model.fk_cache_mode,
            "strict_deterministic_chunking": self.view_model.strict_deterministic_chunking,
            "execution_mode": self.view_model.execution_mode,
            "worker_count": self.view_model.worker_count,
            "max_inflight_chunks": self.view_model.max_inflight_chunks,
            "ipc_queue_size": self.view_model.ipc_queue_size,
            "retry_limit": self.view_model.retry_limit,
            "profile_name": self.view_model.profile_name,
        }
        try:
            Path(output_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Run Center v2 error", _v2_error("Save config", f"could not write config file ({exc})", "choose a writable output path"))
            return
        self.shell.set_status(f"Saved config to {output_path}.")

    def _load_profile(self) -> None:
        input_path = filedialog.askopenfilename(title="Load Run Center v2 config JSON", filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if input_path == "":
            self.shell.set_status("Load config cancelled.")
            return
        try:
            payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            messagebox.showerror("Run Center v2 error", _v2_error("Load config", f"failed to read JSON ({exc})", "choose a valid JSON config file"))
            return
        if not isinstance(payload, dict):
            messagebox.showerror("Run Center v2 error", _v2_error("Load config", "config JSON must be an object", "store config fields in a JSON object"))
            return

        self.schema_path_var.set(str(payload.get("schema_path", "")))
        self.target_tables_var.set(str(payload.get("target_tables", "")))
        self.row_overrides_var.set(str(payload.get("row_overrides_json", "")))
        self.preview_row_target_var.set(str(payload.get("preview_row_target", "500")))
        self.output_mode_var.set(coerce_output_mode(str(payload.get("output_mode", OUTPUT_MODES[0]))))
        self.chunk_size_rows_var.set(str(payload.get("chunk_size_rows", "10000")))
        self.preview_page_size_var.set(str(payload.get("preview_page_size", "500")))
        self.sqlite_batch_size_var.set(str(payload.get("sqlite_batch_size", "5000")))
        self.csv_buffer_rows_var.set(str(payload.get("csv_buffer_rows", "5000")))
        self.fk_cache_mode_var.set(str(payload.get("fk_cache_mode", FK_CACHE_MODES[0])))
        self.strict_chunking_var.set(bool(payload.get("strict_deterministic_chunking", True)))
        self.execution_mode_var.set(coerce_execution_mode(str(payload.get("execution_mode", EXECUTION_MODES[0]))))
        self.worker_count_var.set(str(payload.get("worker_count", "1")))
        self.max_inflight_chunks_var.set(str(payload.get("max_inflight_chunks", "4")))
        self.ipc_queue_size_var.set(str(payload.get("ipc_queue_size", "128")))
        self.retry_limit_var.set(str(payload.get("retry_limit", "1")))
        self.profile_name_var.set(str(payload.get("profile_name", "default_v2_profile")))
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


class ERDDesignerV2Screen(ToolBridgeV2Screen):
    """Feature-C parity bridge for ERD designer."""

    def __init__(self, parent: tk.Widget, app: object, _cfg: AppConfig) -> None:
        super().__init__(
            parent,
            app,
            title="ERD Designer v2",
            launch_label="Open current ERD Designer",
            launch_route="erd_designer",
            description="This v2 bridge keeps redesign navigation consistent while ERD canvas parity remains additive.",
            inspector_title="ERD Bridge Notes",
            inspector_lines=[
                "Current ERD route remains source of truth for schema rendering and editing.",
                "Bridge preserves additive rollout safety for Feature C.",
            ],
        )


class LocationSelectorV2Screen(ToolBridgeV2Screen):
    """Feature-C parity bridge for location selector."""

    def __init__(self, parent: tk.Widget, app: object, _cfg: AppConfig) -> None:
        super().__init__(
            parent,
            app,
            title="Location Selector v2",
            launch_label="Open current Location Selector",
            launch_route="location_selector",
            description="This v2 bridge preserves deterministic map/GeoJSON/sample behavior through the production route.",
            inspector_title="Location Bridge Notes",
            inspector_lines=[
                "Production location selector remains unchanged for deterministic behavior.",
                "Bridge route keeps users in v2 navigation without behavior regressions.",
            ],
        )


class GenerationBehaviorsGuideV2Screen(ToolBridgeV2Screen):
    """Feature-C parity bridge for generation behaviors guide."""

    def __init__(self, parent: tk.Widget, app: object, _cfg: AppConfig) -> None:
        super().__init__(
            parent,
            app,
            title="Generation Guide v2",
            launch_label="Open current Generation Behaviors Guide",
            launch_route="generation_behaviors_guide",
            description="This v2 bridge keeps guidance discoverable while guide content remains canonical and read-only.",
            inspector_title="Guide Bridge Notes",
            inspector_lines=[
                "Current guide content remains canonical and read-only.",
                "Bridge route supports phased migration without semantic changes.",
            ],
        )
