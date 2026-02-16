from __future__ import annotations

import tkinter as tk

from src.config import AppConfig
from src.gui_route_policy import SCHEMA_PRIMARY_ROUTE
from src.gui_schema_project_kit import SchemaProjectDesignerKitScreen

V2_HEADER_BG = "#0f2138"
V2_HEADER_FG = "#f5f5f5"
V2_ACTION_BG = "#d9d2c4"
V2_ACTION_FG = "#1f1f1f"


class SchemaProjectV2Screen(SchemaProjectDesignerKitScreen):
    """Native v2 schema authoring route with canonical schema-editor behavior."""

    def __init__(self, parent: tk.Widget, app: object, cfg: AppConfig) -> None:
        super().__init__(parent, app, cfg)

    def build_header(self):  # type: ignore[override]
        header = tk.Frame(self._root_content, bg=V2_HEADER_BG, height=58)
        header.pack(fill="x", pady=(0, 10))
        header.pack_propagate(False)

        tk.Button(
            header,
            text="Back",
            command=self._on_back_requested,
            bg=V2_ACTION_BG,
            fg=V2_ACTION_FG,
            relief="flat",
            padx=10,
            pady=5,
        ).pack(side="left", padx=(8, 8), pady=8)
        tk.Label(
            header,
            text="Schema Project v2",
            bg=V2_HEADER_BG,
            fg=V2_HEADER_FG,
            font=("Cambria", 16, "bold"),
        ).pack(side="left", pady=8)
        tk.Label(
            header,
            textvariable=self._dirty_indicator_var,
            bg=V2_HEADER_BG,
            fg=V2_HEADER_FG,
            font=("Calibri", 10, "bold"),
        ).pack(side="left", padx=(10, 0), pady=8)

        tk.Button(
            header,
            text="Open Classic",
            command=lambda: self.app.show_screen(SCHEMA_PRIMARY_ROUTE),
            bg=V2_ACTION_BG,
            fg=V2_ACTION_FG,
            relief="flat",
            padx=10,
            pady=5,
        ).pack(side="right", padx=(0, 8), pady=8)
        tk.Button(
            header,
            text="Shortcuts",
            command=self._show_shortcuts_help,
            bg=V2_ACTION_BG,
            fg=V2_ACTION_FG,
            relief="flat",
            padx=10,
            pady=5,
        ).pack(side="right", padx=(0, 8), pady=8)
        return header

    def _on_back_requested(self) -> None:
        if self.confirm_discard_or_save(action_name="returning to Schema Studio v2"):
            self.app.show_screen("schema_studio_v2")
