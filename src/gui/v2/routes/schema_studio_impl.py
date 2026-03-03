from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.config import AppConfig
from src.gui_route_policy import SCHEMA_V2_ROUTE
from src.gui.v2.routes.shell_impl import V2ShellFrame
from src.gui.v2.routes.theme_shared import V2_BG
from src.gui_v2.navigation import DirtyRouteGuard
from src.gui_v2.navigation import guarded_navigation
from src.gui_v2.viewmodels import SchemaStudioViewModel

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

        self.section_tabs = ttk.Notebook(self.shell.workspace)
        self.section_tabs.pack(fill="both", expand=True, padx=10, pady=10)
        self._tab_by_name: dict[str, ttk.Frame] = {}

        self._inspector_by_section = {
            "project": [
                "Project metadata and seed configuration live in schema routes.",
                "Use schema_project_v2 for full schema editing and validation.",
                "Fallback schema routes are hidden and rollback-only in this cycle.",
            ],
            "tables": ["Open schema_project_v2 for table authoring and SCD/business-key controls."],
            "columns": ["Open schema_project_v2 for column generator and params authoring."],
            "relationships": ["Open schema_project_v2 for FK relationship mapping and constraints."],
            "run": ["Use Run Center v2 for diagnostics, plan, and execution."],
        }

        self._build_tab(
            "project",
            "Project",
            lambda: self._navigate_with_guard(SCHEMA_V2_ROUTE, "opening schema project designer"),
        )
        self._build_tab(
            "tables",
            "Tables",
            lambda: self._navigate_with_guard(SCHEMA_V2_ROUTE, "opening table workflow"),
        )
        self._build_tab(
            "columns",
            "Columns",
            lambda: self._navigate_with_guard(SCHEMA_V2_ROUTE, "opening column workflow"),
        )
        self._build_tab(
            "relationships",
            "Relationships",
            lambda: self._navigate_with_guard(SCHEMA_V2_ROUTE, "opening relationship workflow"),
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
        screens = getattr(self.app, "screens", {})
        screen = screens.get(SCHEMA_V2_ROUTE)
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
            if result.reason == "guard_error":
                self.shell.set_status("Navigation blocked: unable to confirm schema changes. Retry after validating schema state.")
            elif result.reason == "user_cancelled":
                self.shell.set_status("Navigation cancelled: unsaved changes remain in schema designer.")
            else:
                self.shell.set_status("Navigation blocked. Retry after resolving schema designer unsaved changes.")

    def select_section(self, section_key: str) -> None:
        if section_key not in self._tab_by_name:
            return
        self.view_model.selected_section = section_key
        self.shell.set_nav_active(section_key)
        self.section_tabs.select(self._tab_by_name[section_key])
        self.shell.set_inspector(f"{section_key.title()} Inspector", self._inspector_by_section.get(section_key, []))
        self.shell.set_status(f"Schema Studio v2: viewing {section_key} section.")


__all__ = ["SchemaStudioV2Screen"]
