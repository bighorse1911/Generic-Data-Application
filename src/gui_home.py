from __future__ import annotations

from collections.abc import Callable
import tkinter as tk
from tkinter import ttk

from src.config import AppConfig
from src.gui_kit.command_palette import CommandPalette
from src.gui_kit.command_palette import CommandPaletteRegistry
from src.gui_kit.preferences import WorkspacePreferencesStore
from src.gui_route_policy import ERD_V2_ROUTE
from src.gui_route_policy import GENERATION_GUIDE_V2_ROUTE
from src.gui_route_policy import HOME_V2_ROUTE
from src.gui_route_policy import LOCATION_V2_ROUTE
from src.gui_route_policy import ORCHESTRATOR_V2_ROUTE
from src.gui_route_policy import PERFORMANCE_V2_ROUTE
from src.gui_route_policy import RUN_CENTER_V2_ROUTE
from src.gui_route_policy import SCHEMA_STUDIO_V2_ROUTE
from src.gui_route_policy import SCHEMA_V2_ROUTE
from src.gui_tools import GENERATION_BEHAVIOR_GUIDE
from src.gui_v2_execution_orchestrator import ExecutionOrchestratorV2Screen
from src.gui_v2_performance_workbench import PerformanceWorkbenchV2Screen
from src.gui_v2_redesign import ERDDesignerV2Screen
from src.gui_v2_redesign import GenerationBehaviorsGuideV2Screen
from src.gui_v2_redesign import HomeV2Screen
from src.gui_v2_redesign import LocationSelectorV2Screen
from src.gui_v2_redesign import RunCenterV2Screen
from src.gui_v2_redesign import SchemaStudioV2Screen
from src.gui_v2_schema_project import SchemaProjectV2Screen

_UNSET = object()
MAX_IDLE_PREFETCH_ROUTES = 2

ROUTE_DISPLAY_NAMES: dict[str, str] = {
    HOME_V2_ROUTE: "Home v2",
    SCHEMA_STUDIO_V2_ROUTE: "Schema Studio v2",
    SCHEMA_V2_ROUTE: "Schema Project v2",
    RUN_CENTER_V2_ROUTE: "Run Center v2",
    PERFORMANCE_V2_ROUTE: "Performance Workbench v2",
    ORCHESTRATOR_V2_ROUTE: "Execution Orchestrator v2",
    ERD_V2_ROUTE: "ERD Designer v2",
    LOCATION_V2_ROUTE: "Location Selector v2",
    GENERATION_GUIDE_V2_ROUTE: "Generation Guide v2",
}

SCREEN_COMMAND_ACTIONS: dict[str, tuple[tuple[str, str, str, tuple[str, ...]], ...]] = {
    SCHEMA_V2_ROUTE: (
        ("load", "Load project JSON", "_start_load_project_async", ("load", "schema", "json")),
        ("save", "Save project JSON", "_start_save_project_async", ("save", "schema", "json")),
        ("validate", "Run validation", "_run_validation_full", ("validate", "schema", "check")),
        ("generate", "Generate preview rows", "_on_generate_project", ("generate", "preview", "rows")),
    ),
    RUN_CENTER_V2_ROUTE: (
        ("load", "Load schema", "_load_schema", ("load", "schema")),
        ("save", "Save run config", "_save_profile", ("save", "profile", "run")),
        ("estimate", "Estimate workload", "_run_estimate", ("estimate", "diagnostics")),
        ("plan", "Build partition plan", "_run_build_plan", ("plan", "partition")),
        ("benchmark", "Run benchmark", "_start_benchmark", ("benchmark", "performance")),
        ("generate", "Start run", "_start_generation", ("generate", "run", "start")),
    ),
    PERFORMANCE_V2_ROUTE: (
        ("load", "Load schema", "_load_schema", ("load", "schema")),
        ("save", "Save profile", "_save_profile", ("save", "profile")),
        ("estimate", "Estimate workload", "_estimate_workload", ("estimate", "diagnostics")),
        ("plan", "Build chunk plan", "_build_chunk_plan", ("plan", "chunk")),
        ("benchmark", "Run benchmark", "_start_run_benchmark", ("benchmark", "performance")),
        ("generate", "Generate with strategy", "_start_generate_with_strategy", ("generate", "strategy")),
    ),
    ORCHESTRATOR_V2_ROUTE: (
        ("load", "Load schema", "_load_schema", ("load", "schema")),
        ("save", "Save run config", "_save_run_config", ("save", "run", "config")),
        ("plan", "Build partition plan", "_build_plan", ("plan", "partition")),
        ("generate", "Start run", "_start_run", ("generate", "run", "start")),
    ),
}

IDLE_PREFETCH_ROUTES: dict[str, tuple[str, ...]] = {
    HOME_V2_ROUTE: (
        SCHEMA_STUDIO_V2_ROUTE,
        RUN_CENTER_V2_ROUTE,
        SCHEMA_V2_ROUTE,
    ),
    SCHEMA_STUDIO_V2_ROUTE: (
        SCHEMA_V2_ROUTE,
        RUN_CENTER_V2_ROUTE,
    ),
    SCHEMA_V2_ROUTE: (
        RUN_CENTER_V2_ROUTE,
        SCHEMA_STUDIO_V2_ROUTE,
    ),
    RUN_CENTER_V2_ROUTE: (
        PERFORMANCE_V2_ROUTE,
        ORCHESTRATOR_V2_ROUTE,
    ),
    PERFORMANCE_V2_ROUTE: (
        RUN_CENTER_V2_ROUTE,
        ORCHESTRATOR_V2_ROUTE,
    ),
    ORCHESTRATOR_V2_ROUTE: (
        RUN_CENTER_V2_ROUTE,
        PERFORMANCE_V2_ROUTE,
    ),
    ERD_V2_ROUTE: (
        HOME_V2_ROUTE,
        LOCATION_V2_ROUTE,
    ),
    LOCATION_V2_ROUTE: (
        HOME_V2_ROUTE,
        ERD_V2_ROUTE,
    ),
    GENERATION_GUIDE_V2_ROUTE: (
        HOME_V2_ROUTE,
        SCHEMA_STUDIO_V2_ROUTE,
    ),
}


class LazyScreenRegistry(dict[str, ttk.Frame | object]):
    """Route->screen mapping that creates screens on first indexed access."""

    def __init__(
        self,
        *,
        factories: dict[str, Callable[[], ttk.Frame]],
        create_screen: Callable[[str], ttk.Frame],
    ) -> None:
        self._factories = dict(factories)
        self._create_screen = create_screen
        super().__init__({route: _UNSET for route in self._factories})

    def __getitem__(self, key: str) -> ttk.Frame:
        value = dict.__getitem__(self, key)
        if value is _UNSET:
            screen = self._create_screen(key)
            dict.__setitem__(self, key, screen)
            return screen
        return value  # type: ignore[return-value]

    def get(self, key: str, default=None):  # type: ignore[override]
        if key not in self:
            return default
        value = dict.__getitem__(self, key)
        if value is _UNSET:
            return default
        return value

    def values(self):  # type: ignore[override]
        return [self[key] for key in self.keys()]

    def items(self):  # type: ignore[override]
        return [(key, self[key]) for key in self.keys()]

    def is_loaded(self, key: str) -> bool:
        if key not in self:
            return False
        return dict.__getitem__(self, key) is not _UNSET

    def loaded_routes(self) -> tuple[str, ...]:
        return tuple(key for key in self.keys() if self.is_loaded(key))


class App(ttk.Frame):
    """V2-only app container that manages screen registration and switching."""

    def __init__(self, root: tk.Tk, cfg: AppConfig) -> None:
        super().__init__(root)
        self.root = root
        self.cfg = cfg

        self.root.title("Generic Data Application")
        self.root.geometry("960x540")

        self.pack(fill="both", expand=True)

        self.screen_container = ttk.Frame(self)
        self.screen_container.pack(fill="both", expand=True)
        self.workspace_preferences = WorkspacePreferencesStore()
        self._current_screen_name: str | None = None
        self._current_screen_frame: ttk.Frame | None = None
        self._prefetch_job_id: str | None = None
        self._prefetch_queue: list[str] = []
        self._global_shortcut_bindings: dict[str, str] = {}
        self.bind("<Destroy>", self._on_destroy, add="+")

        self._screen_factories: dict[str, Callable[[], ttk.Frame]] = {
            HOME_V2_ROUTE: lambda: HomeV2Screen(self.screen_container, self),
            SCHEMA_STUDIO_V2_ROUTE: lambda: SchemaStudioV2Screen(self.screen_container, self, cfg),
            SCHEMA_V2_ROUTE: lambda: SchemaProjectV2Screen(self.screen_container, self, cfg),
            RUN_CENTER_V2_ROUTE: lambda: RunCenterV2Screen(self.screen_container, self, cfg),
            PERFORMANCE_V2_ROUTE: lambda: PerformanceWorkbenchV2Screen(self.screen_container, self, cfg),
            ORCHESTRATOR_V2_ROUTE: lambda: ExecutionOrchestratorV2Screen(self.screen_container, self, cfg),
            ERD_V2_ROUTE: lambda: ERDDesignerV2Screen(self.screen_container, self, cfg),
            LOCATION_V2_ROUTE: lambda: LocationSelectorV2Screen(self.screen_container, self, cfg),
            GENERATION_GUIDE_V2_ROUTE: lambda: GenerationBehaviorsGuideV2Screen(self.screen_container, self, cfg),
        }

        self.screens = LazyScreenRegistry(
            factories=self._screen_factories,
            create_screen=self._create_screen,
        )
        self.command_palette = CommandPalette(
            self,
            registry_factory=self._build_command_palette_registry,
            title="Command Palette",
        )
        self._bind_global_shortcuts()

        self.screen_container.rowconfigure(0, weight=1)
        self.screen_container.columnconfigure(0, weight=1)

        self.show_screen(HOME_V2_ROUTE)

    def _create_screen(self, name: str) -> ttk.Frame:
        if name not in self._screen_factories:
            available = ", ".join(sorted(self._screen_factories.keys()))
            raise KeyError(
                f"Unknown screen '{name}' in App._create_screen. "
                f"Available screens: {available}. "
                "Fix: call _create_screen() with one of the available route keys."
            )
        screen = self._screen_factories[name]()
        screen.grid(row=0, column=0, sticky="nsew")
        return screen

    def _cancel_prefetch(self) -> None:
        if self._prefetch_job_id is None:
            return
        try:
            self.root.after_cancel(self._prefetch_job_id)
        except tk.TclError:
            pass
        finally:
            self._prefetch_job_id = None
            self._prefetch_queue = []

    def _schedule_idle_prefetch(self, current_route: str) -> None:
        if not self.winfo_exists():
            return
        candidates = IDLE_PREFETCH_ROUTES.get(current_route, ())
        queue: list[str] = []
        for route in candidates:
            if route == current_route:
                continue
            if route not in self.screens:
                continue
            if self.screens.is_loaded(route):
                continue
            queue.append(route)
            if len(queue) >= MAX_IDLE_PREFETCH_ROUTES:
                break
        self._cancel_prefetch()
        if not queue:
            return
        self._prefetch_queue = queue
        self._prefetch_job_id = self.root.after_idle(self._prefetch_next)

    def _prefetch_next(self) -> None:
        self._prefetch_job_id = None
        if not self.winfo_exists():
            self._prefetch_queue = []
            return
        if not self._prefetch_queue:
            return
        route = self._prefetch_queue.pop(0)
        try:
            _ = self.screens[route]
        except Exception:
            # Prefetch is best-effort and must never break active navigation.
            pass
        current_frame = self._current_screen_frame
        if current_frame is not None and current_frame.winfo_exists():
            # Keep active route visible when background-prefetched frames are gridded.
            current_frame.tkraise()
        if self._prefetch_queue:
            self._prefetch_job_id = self.root.after_idle(self._prefetch_next)

    def _on_destroy(self, event) -> None:
        if event.widget is self:
            self.command_palette.close()
            self._cancel_prefetch()
            self._unbind_global_shortcuts()

    def _bind_global_shortcuts(self) -> None:
        for sequence in ("<Control-k>", "<Control-K>", "<Command-k>", "<Command-K>"):
            bind_id = self.root.bind(sequence, self._on_open_command_palette_shortcut, add="+")
            if bind_id:
                self._global_shortcut_bindings[sequence] = bind_id

    def _unbind_global_shortcuts(self) -> None:
        for sequence, bind_id in list(self._global_shortcut_bindings.items()):
            try:
                self.root.unbind(sequence, bind_id)
            except tk.TclError:
                pass
        self._global_shortcut_bindings.clear()

    def _build_command_palette_registry(self) -> CommandPaletteRegistry:
        registry = CommandPaletteRegistry()
        for route, label in ROUTE_DISPLAY_NAMES.items():
            registry.register_action(
                f"route:{route}",
                f"Go to {label}",
                lambda route_key=route: self.show_screen(route_key),
                subtitle="Route jump",
                keywords=("route", "jump", "navigate", route, label),
            )

        current_route = self._current_screen_name
        if current_route is None:
            return registry
        screen = self.screens.get(current_route)
        if screen is None:
            return registry

        action_specs = SCREEN_COMMAND_ACTIONS.get(current_route, ())
        route_label = ROUTE_DISPLAY_NAMES.get(current_route, current_route)
        for action_key, title, method_name, keywords in action_specs:
            callback = getattr(screen, method_name, None)
            if not callable(callback):
                continue
            registry.register_action(
                f"{current_route}:{action_key}",
                title,
                callback,
                subtitle=f"{route_label} action",
                keywords=keywords,
            )
        return registry

    def _on_open_command_palette_shortcut(self, _event=None) -> str:
        self.open_command_palette()
        return "break"

    def open_command_palette(self) -> None:
        self.command_palette.open()

    def show_screen(self, name: str) -> None:
        if name not in self.screens:
            available = ", ".join(sorted(self.screens.keys()))
            raise KeyError(
                f"Unknown screen '{name}' in App.show_screen. "
                f"Available screens: {available}. "
                "Fix: call show_screen() with one of the available names."
            )
        screen = self.screens[name]
        if self._current_screen_frame is screen:
            screen.tkraise()
            self._current_screen_name = name
            return

        if self._current_screen_frame is not None:
            on_hide = getattr(self._current_screen_frame, "on_hide", None)
            if callable(on_hide):
                on_hide()

        screen.tkraise()
        on_show = getattr(screen, "on_show", None)
        if callable(on_show):
            on_show()
        self._current_screen_name = name
        self._current_screen_frame = screen
        self._schedule_idle_prefetch(name)

    def go_home(self) -> None:
        self.show_screen(HOME_V2_ROUTE)

    @property
    def current_screen_name(self) -> str | None:
        return self._current_screen_name
