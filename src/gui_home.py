from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk

from src.config import AppConfig
from src.gui_kit.accessibility import FocusController
from src.gui_execution_orchestrator import ExecutionOrchestratorScreen
from src.gui_kit.error_surface import ErrorSurface
from src.gui_kit.error_surface import show_error_dialog
from src.gui_kit.error_surface import show_warning_dialog
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
from src.gui_route_policy import SCHEMA_DEPRECATED_ROUTES
from src.gui_route_policy import SCHEMA_FALLBACK_ROUTES
from src.gui_route_policy import SCHEMA_PRIMARY_ROUTE
from src.gui_schema_project import SchemaProjectDesignerScreen
from src.gui_schema_project_kit import SchemaProjectDesignerKitScreen
from src.gui_tools import ERDDesignerToolFrame
from src.gui_tools import GENERATION_BEHAVIOR_GUIDE
from src.gui_tools import GenerationGuideToolFrame
from src.gui_tools import LocationSelectorToolFrame
from src.gui_tools.run_workflow_view import RunWorkflowCapabilities
from src.gui_tools.run_workflow_view import RunWorkflowSurface
from src.gui_v2_redesign import ERDDesignerV2BridgeScreen
from src.gui_v2_redesign import ERDDesignerV2Screen
from src.gui_v2_redesign import GenerationBehaviorsGuideV2BridgeScreen
from src.gui_v2_redesign import GenerationBehaviorsGuideV2Screen
from src.gui_v2_redesign import HomeV2Screen
from src.gui_v2_redesign import LocationSelectorV2BridgeScreen
from src.gui_v2_redesign import LocationSelectorV2Screen
from src.gui_v2_redesign import RunCenterV2Screen
from src.gui_v2_redesign import SchemaStudioV2Screen
from src.performance_scaling import BenchmarkResult
from src.performance_scaling import ChunkPlanEntry
from src.performance_scaling import PerformanceRunCancelled
from src.performance_scaling import RuntimeEvent
from src.performance_scaling import StrategyRunResult
from src.schema_project_io import load_project_from_json


class GenerationBehaviorsGuideScreen(GenerationGuideToolFrame):
    """Read-only reference page for generation behaviors supported by the app."""

    def __init__(self, parent: tk.Widget, app: "App") -> None:
        super().__init__(parent, app)


class ERDDesignerScreen(ERDDesignerToolFrame):
    """Schema-to-diagram view for table/column/FK relationship inspection."""

    def __init__(self, parent: tk.Widget, app: "App", cfg: AppConfig) -> None:
        super().__init__(parent, app, cfg)


class LocationSelectorScreen(LocationSelectorToolFrame):
    """Interactive map page for selecting a center point and radius-based GeoJSON."""

    def __init__(self, parent: tk.Widget, app: "App", cfg: AppConfig) -> None:
        super().__init__(parent, app, cfg)


class SchemaProjectLegacyFallbackScreen(SchemaProjectDesignerScreen):
    """Hidden rollback fallback for legacy schema authoring route."""
    ERROR_SURFACE_CONTEXT = "Schema project legacy"
    ERROR_DIALOG_TITLE = "Schema project legacy error"
    WARNING_DIALOG_TITLE = "Schema project legacy warning"

    def on_show(self) -> None:
        if "schema_project_legacy" in SCHEMA_DEPRECATED_ROUTES and hasattr(self, "status_var"):
            self.status_var.set(
                "Schema Project Legacy is deprecated and retained as hidden rollback fallback. "
                "Fix: use 'schema_project' for primary authoring."
            )


class PerformanceWorkbenchScreen(ttk.Frame):
    """Phase-1 performance profiling and workload diagnostics screen."""

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
        self.surface.clear_tree(self.diagnostics_tree)
        for estimate in estimates:
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

    def _populate_chunk_plan(self, entries: list[ChunkPlanEntry]) -> None:
        self.surface.clear_tree(self.chunk_plan_tree)
        for entry in entries:
            partition_id = f"{entry.table_name}|stage={entry.stage}|chunk={entry.chunk_index}"
            self.chunk_plan_tree.insert(
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
        self.surface.set_status(
            "Estimate complete: "
            f"rows={diagnostics.summary.total_rows}, memory={diagnostics.summary.total_memory_mb:.3f} MB, "
            f"write={diagnostics.summary.total_write_mb:.3f} MB, time={diagnostics.summary.total_seconds:.3f} s, "
            f"highest risk={diagnostics.summary.highest_risk}."
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
        self.surface.set_status(
            f"Chunk plan ready: tables={len({e.table_name for e in plan_entries})}, "
            f"chunks={len(plan_entries)}, rows={total_rows}, max stage={max_stage}."
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

    def _on_benchmark_done(self, result: BenchmarkResult) -> None:
        self.lifecycle.transition_complete("Benchmark complete")
        self._populate_estimates(result.estimates)
        self._populate_chunk_plan(result.chunk_plan)
        self.surface.set_status(
            "Benchmark complete: "
            f"tables={len(result.selected_tables)}, chunks={result.chunk_summary.total_chunks}, "
            f"rows={result.chunk_summary.total_rows}, risk={result.estimate_summary.highest_risk}."
        )

    def _on_generate_done(self, result: StrategyRunResult) -> None:
        self.lifecycle.transition_complete("Generation complete")
        csv_count = len(result.csv_paths)
        sqlite_rows = sum(result.sqlite_counts.values())
        self.surface.set_status(
            "Generation complete: "
            f"tables={len(result.selected_tables)}, rows={result.total_rows}, "
            f"csv_files={csv_count}, sqlite_rows={sqlite_rows}."
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
        self.surface.set_status(f"Saved performance profile to {output_path}.")

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
        self.surface.set_status(f"Loaded performance profile from {profile_path}.")


class HomeScreen(ttk.Frame):
    """Home screen focused on the app workflow routes."""

    def __init__(self, parent: tk.Widget, app: "App") -> None:
        super().__init__(parent, padding=16)
        self.app = app

        title = ttk.Label(self, text="Generic Data Application", font=("Segoe UI", 18, "bold"))
        title.pack(anchor="w", pady=(0, 8))

        subtitle = ttk.Label(
            self,
            text="Schema Project MVP: design multi-table schemas and generate relational data.",
        )
        subtitle.pack(anchor="w", pady=(0, 16))

        card = ttk.LabelFrame(self, text="Tool", padding=12)
        card.pack(fill="x")

        ttk.Button(
            card,
            text="Schema Project Designer (Production) -> modular layout, tables/FKs/generation/JSON/SQLite",
            command=lambda: self.app.show_screen("schema_project"),
        ).pack(fill="x", pady=6)

        ttk.Button(
            card,
            text="Data Generation Behaviors Guide -> explanation and setup patterns",
            command=lambda: self.app.show_screen("generation_behaviors_guide"),
        ).pack(fill="x", pady=6)

        ttk.Button(
            card,
            text="ERD Designer -> schema JSON to interactive entity relationship diagram",
            command=lambda: self.app.show_screen("erd_designer"),
        ).pack(fill="x", pady=6)

        ttk.Button(
            card,
            text="Location Selector -> map point/radius to GeoJSON and latitude/longitude samples",
            command=lambda: self.app.show_screen("location_selector"),
        ).pack(fill="x", pady=6)

        ttk.Button(
            card,
            text="Performance Workbench -> configure chunking profile and estimate workload",
            command=lambda: self.app.show_screen("performance_workbench"),
        ).pack(fill="x", pady=6)

        ttk.Button(
            card,
            text="Execution Orchestrator -> multiprocessing partition planning and worker run monitor",
            command=lambda: self.app.show_screen("execution_orchestrator"),
        ).pack(fill="x", pady=6)

        ttk.Button(
            card,
            text=(
                "Visual Redesign Preview (v2) -> home_v2 / schema_studio_v2 / run_center_v2 "
                "/ erd_designer_v2 / location_selector_v2 / generation_behaviors_guide_v2"
            ),
            command=lambda: self.app.show_screen("home_v2"),
        ).pack(fill="x", pady=6)


class App(ttk.Frame):
    """App container that manages screens and switches between them."""

    def __init__(self, root: tk.Tk, cfg: AppConfig) -> None:
        super().__init__(root)
        self.root = root
        self.cfg = cfg

        self.root.title("Generic Data Application")
        self.root.geometry("960x540")

        self.pack(fill="both", expand=True)

        self.screen_container = ttk.Frame(self)
        self.screen_container.pack(fill="both", expand=True)

        self.screens: dict[str, ttk.Frame] = {}
        self.screens["home"] = HomeScreen(self.screen_container, self)
        primary_schema_screen = SchemaProjectDesignerKitScreen(self.screen_container, self, cfg)
        legacy_schema_screen = SchemaProjectLegacyFallbackScreen(self.screen_container, self, cfg)
        fallback_kit_route, fallback_legacy_route = SCHEMA_FALLBACK_ROUTES
        self.screens[SCHEMA_PRIMARY_ROUTE] = primary_schema_screen
        self.screens[fallback_kit_route] = primary_schema_screen
        self.screens[fallback_legacy_route] = legacy_schema_screen
        self.screens["generation_behaviors_guide"] = GenerationBehaviorsGuideScreen(self.screen_container, self)
        self.screens["erd_designer"] = ERDDesignerScreen(self.screen_container, self, cfg)
        self.screens["location_selector"] = LocationSelectorScreen(self.screen_container, self, cfg)
        self.screens["performance_workbench"] = PerformanceWorkbenchScreen(self.screen_container, self, cfg)
        self.screens["execution_orchestrator"] = ExecutionOrchestratorScreen(self.screen_container, self, cfg)
        self.screens["home_v2"] = HomeV2Screen(self.screen_container, self)
        self.screens["schema_studio_v2"] = SchemaStudioV2Screen(self.screen_container, self, cfg)
        self.screens["run_center_v2"] = RunCenterV2Screen(self.screen_container, self, cfg)
        self.screens["erd_designer_v2"] = ERDDesignerV2Screen(self.screen_container, self, cfg)
        self.screens["location_selector_v2"] = LocationSelectorV2Screen(self.screen_container, self, cfg)
        self.screens["generation_behaviors_guide_v2"] = GenerationBehaviorsGuideV2Screen(
            self.screen_container,
            self,
            cfg,
        )
        self.screens["erd_designer_v2_bridge"] = ERDDesignerV2BridgeScreen(self.screen_container, self, cfg)
        self.screens["location_selector_v2_bridge"] = LocationSelectorV2BridgeScreen(self.screen_container, self, cfg)
        self.screens["generation_behaviors_guide_v2_bridge"] = GenerationBehaviorsGuideV2BridgeScreen(
            self.screen_container,
            self,
            cfg,
        )

        gridded_frames: set[int] = set()
        for frame in self.screens.values():
            frame_id = id(frame)
            if frame_id in gridded_frames:
                continue
            frame.grid(row=0, column=0, sticky="nsew")
            gridded_frames.add(frame_id)

        self.screen_container.rowconfigure(0, weight=1)
        self.screen_container.columnconfigure(0, weight=1)

        self.show_screen("home")

    def show_screen(self, name: str) -> None:
        if name not in self.screens:
            available = ", ".join(sorted(self.screens.keys()))
            raise KeyError(
                f"Unknown screen '{name}' in App.show_screen. "
                f"Available screens: {available}. "
                "Fix: call show_screen() with one of the available names."
            )
        screen = self.screens[name]
        on_show = getattr(screen, "on_show", None)
        if callable(on_show):
            on_show()
        screen.tkraise()

    def go_home(self) -> None:
        self.show_screen("home")
