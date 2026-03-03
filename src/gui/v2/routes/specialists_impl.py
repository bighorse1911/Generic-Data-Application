from __future__ import annotations

import tkinter as tk

from src.config import AppConfig
from src.gui_tools import ERDDesignerToolFrame
from src.gui_tools import GenerationGuideToolFrame
from src.gui_tools import LocationSelectorToolFrame
from src.gui.v2.routes.adapters import _BackToRouteAdapter
from src.gui.v2.routes.shell_impl import V2ShellFrame
from src.gui.v2.routes.theme_shared import V2_BG
from src.gui_v2.viewmodels import ERDDesignerV2ViewModel
from src.gui_v2.viewmodels import GenerationGuideV2ViewModel
from src.gui_v2.viewmodels import LocationSelectorV2ViewModel

class ERDDesignerV2Screen(tk.Frame):
    """Native v2 route for ERD designer behavior."""

    def __init__(self, parent: tk.Widget, app: object, cfg: AppConfig) -> None:
        super().__init__(parent, bg=V2_BG)
        self.app = app
        self.view_model = ERDDesignerV2ViewModel()
        self.shell = V2ShellFrame(self, title="ERD Designer v2", on_back=lambda: self.app.show_screen("home_v2"))
        self.shell.pack(fill="both", expand=True)
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



__all__ = [
    "ERDDesignerV2Screen",
    "LocationSelectorV2Screen",
    "GenerationBehaviorsGuideV2Screen",
]
