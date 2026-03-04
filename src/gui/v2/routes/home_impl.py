from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from src.experimental.pyqt_schema_project.launcher import (
    is_experiment_enabled,
    launch_pyqt_schema_project,
)
from src.gui_route_policy import ORCHESTRATOR_V2_ROUTE
from src.gui_route_policy import PERFORMANCE_V2_ROUTE
from src.gui_route_policy import SCHEMA_V2_ROUTE
from src.gui_kit.theme_tokens import V2_THEME
from src.gui_kit.theme_tokens import v2_button_options
from src.gui.v2.routes.theme_shared import V2_BG
from src.gui.v2.routes.theme_shared import V2_HEADER_BG
from src.gui.v2.routes.theme_shared import V2_PANEL

class HomeV2Screen(tk.Frame):
    """Feature-C home with v2 routes for authoring, runtime, and native specialist tools."""

    def __init__(self, parent: tk.Widget, app: object) -> None:
        super().__init__(parent, bg=V2_BG)
        spacing = V2_THEME.spacing
        colors = V2_THEME.colors
        type_scale = V2_THEME.type_scale
        self.app = app

        header = tk.Frame(self, bg=V2_HEADER_BG, height=68)
        header.pack(fill="x", padx=spacing.xl, pady=(spacing.xl, spacing.md))
        header.pack_propagate(False)

        tk.Label(
            header,
            text="Home v2 - Full Visual Redesign",
            bg=V2_HEADER_BG,
            fg=colors.header_fg,
            font=type_scale.display_title,
        ).pack(side="left", pady=spacing.md)

        tk.Label(
            self,
            text=(
                "Feature C routes through v2 pages with runtime integration and native specialist "
                "tool pages."
            ),
            bg=V2_BG,
            fg=colors.text_primary,
            anchor="w",
            justify="left",
            font=type_scale.body,
        ).pack(fill="x", padx=spacing.xxl, pady=(0, spacing.md))

        cards_host = tk.Frame(self, bg=V2_BG)
        cards_host.pack(fill="both", expand=True, padx=spacing.xl, pady=(0, spacing.xl))
        cards_host.columnconfigure(0, weight=1)
        cards_host.rowconfigure(0, weight=1)

        self.cards_canvas = tk.Canvas(cards_host, bg=V2_BG, highlightthickness=0, bd=0)
        self.cards_canvas.grid(row=0, column=0, sticky="nsew")
        cards_scroll = ttk.Scrollbar(cards_host, orient="vertical", command=self.cards_canvas.yview)
        cards_scroll.grid(row=0, column=1, sticky="ns")
        self.cards_canvas.configure(yscrollcommand=cards_scroll.set)

        self.cards_frame = tk.Frame(self.cards_canvas, bg=V2_BG)
        self._cards_window = self.cards_canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")

        self.cards_frame.bind("<Configure>", self._on_cards_frame_configure)
        self.cards_canvas.bind("<Configure>", self._on_cards_canvas_configure)

        self._add_card(
            self.cards_frame,
            "Schema Studio v2",
            "Authoring navigation shell with guarded transitions to schema design routes.",
            lambda: self.app.show_screen("schema_studio_v2"),
        )
        self._add_card(
            self.cards_frame,
            "Schema Project v2",
            "Native v2 schema authoring route with canonical validation and generation behavior.",
            lambda: self.app.show_screen(SCHEMA_V2_ROUTE),
        )
        self._add_card(
            self.cards_frame,
            "Run Center v2",
            "Integrated diagnostics, planning, benchmark, and multiprocess execution flow.",
            lambda: self.app.show_screen("run_center_v2"),
        )
        self._add_card(
            self.cards_frame,
            "Performance Workbench v2",
            "Native v2 strategy estimate/benchmark/generate route.",
            lambda: self.app.show_screen(PERFORMANCE_V2_ROUTE),
        )
        self._add_card(
            self.cards_frame,
            "Execution Orchestrator v2",
            "Native v2 multiprocess planning and worker monitoring route.",
            lambda: self.app.show_screen(ORCHESTRATOR_V2_ROUTE),
        )
        self._add_card(
            self.cards_frame,
            "ERD Designer v2",
            "Native v2 ERD workflow with canonical schema/render/export behavior contracts.",
            lambda: self.app.show_screen("erd_designer_v2"),
        )
        self._add_card(
            self.cards_frame,
            "Location Selector v2",
            "Native v2 location workflow for map selection, GeoJSON output, and deterministic samples.",
            lambda: self.app.show_screen("location_selector_v2"),
        )
        self._add_card(
            self.cards_frame,
            "Generation Guide v2",
            "Native v2 read-only guide for generation configuration patterns.",
            lambda: self.app.show_screen("generation_behaviors_guide_v2"),
        )
        if is_experiment_enabled():
            self._add_card(
                self.cards_frame,
                "Schema Project PyQt Experiment",
                "Debug-only optional launcher for isolated PyQt schema-page experimentation.",
                self._launch_pyqt_experiment,
            )

    def _on_cards_frame_configure(self, _event) -> None:
        self.cards_canvas.configure(scrollregion=self.cards_canvas.bbox("all"))

    def _on_cards_canvas_configure(self, event) -> None:
        self.cards_canvas.itemconfigure(self._cards_window, width=event.width)

    def _add_card(self, parent: tk.Widget, title: str, detail: str, command) -> None:
        spacing = V2_THEME.spacing
        colors = V2_THEME.colors
        type_scale = V2_THEME.type_scale
        card = tk.Frame(parent, bg=V2_PANEL, bd=1, relief="solid", highlightthickness=0)
        card.pack(fill="x", pady=(0, spacing.md))

        tk.Label(
            card,
            text=title,
            bg=V2_PANEL,
            fg=colors.text_primary,
            font=type_scale.section_title,
            anchor="w",
        ).pack(fill="x", padx=spacing.lg + spacing.xs, pady=(spacing.md, spacing.xs))

        tk.Label(
            card,
            text=detail,
            bg=V2_PANEL,
            fg=colors.text_muted,
            justify="left",
            anchor="w",
            wraplength=820,
            font=type_scale.body_small,
        ).pack(fill="x", padx=spacing.lg + spacing.xs, pady=(0, spacing.sm))

        tk.Button(
            card,
            text="Open",
            command=command,
            padx=spacing.lg,
            pady=spacing.sm - spacing.xs,
            **v2_button_options("primary"),
        ).pack(anchor="e", padx=spacing.lg + spacing.xs, pady=(0, spacing.md))

    def _launch_pyqt_experiment(self) -> None:
        ok, message = launch_pyqt_schema_project()
        title = "Schema Project PyQt Experiment"
        if ok:
            messagebox.showinfo(title, message)
            return
        messagebox.showwarning(title, message)


__all__ = ["HomeV2Screen"]
