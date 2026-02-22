from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.config import AppConfig
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
        self._current_screen_name: str | None = None
        self._current_screen_frame: ttk.Frame | None = None

        self.screens: dict[str, ttk.Frame] = {
            HOME_V2_ROUTE: HomeV2Screen(self.screen_container, self),
            SCHEMA_STUDIO_V2_ROUTE: SchemaStudioV2Screen(self.screen_container, self, cfg),
            SCHEMA_V2_ROUTE: SchemaProjectV2Screen(self.screen_container, self, cfg),
            RUN_CENTER_V2_ROUTE: RunCenterV2Screen(self.screen_container, self, cfg),
            PERFORMANCE_V2_ROUTE: PerformanceWorkbenchV2Screen(self.screen_container, self, cfg),
            ORCHESTRATOR_V2_ROUTE: ExecutionOrchestratorV2Screen(self.screen_container, self, cfg),
            ERD_V2_ROUTE: ERDDesignerV2Screen(self.screen_container, self, cfg),
            LOCATION_V2_ROUTE: LocationSelectorV2Screen(self.screen_container, self, cfg),
            GENERATION_GUIDE_V2_ROUTE: GenerationBehaviorsGuideV2Screen(self.screen_container, self, cfg),
        }

        for frame in self.screens.values():
            frame.grid(row=0, column=0, sticky="nsew")

        self.screen_container.rowconfigure(0, weight=1)
        self.screen_container.columnconfigure(0, weight=1)

        self.show_screen(HOME_V2_ROUTE)

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

    def go_home(self) -> None:
        self.show_screen(HOME_V2_ROUTE)

    @property
    def current_screen_name(self) -> str | None:
        return self._current_screen_name
