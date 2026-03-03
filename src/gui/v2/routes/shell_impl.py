from __future__ import annotations

import tkinter as tk

from src.gui_kit.theme_tokens import V2_THEME
from src.gui_kit.theme_tokens import v2_button_options
from src.gui.v2.routes.theme_shared import V2_BG
from src.gui.v2.routes.theme_shared import V2_HEADER_BG
from src.gui.v2.routes.theme_shared import V2_INSPECTOR_BG
from src.gui.v2.routes.theme_shared import V2_NAV_BG
from src.gui.v2.routes.theme_shared import V2_PANEL

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
        spacing = V2_THEME.spacing
        type_scale = V2_THEME.type_scale
        colors = V2_THEME.colors
        self._nav_buttons: dict[str, tk.Button] = {}
        self._active_nav_key: str | None = None

        self.header = tk.Frame(self, bg=V2_HEADER_BG, height=56)
        self.header.pack(fill="x", padx=spacing.lg, pady=(spacing.lg, spacing.sm))
        self.header.pack_propagate(False)

        self.back_btn = tk.Button(
            self.header,
            text="Back",
            command=on_back,
            padx=spacing.lg,
            pady=spacing.sm - spacing.xs,
            **v2_button_options("secondary"),
        )
        self.back_btn.pack(side="left", padx=(spacing.sm, spacing.md), pady=spacing.sm)

        self.title_label = tk.Label(
            self.header,
            text=title,
            bg=V2_HEADER_BG,
            fg=colors.header_fg,
            font=type_scale.page_title,
        )
        self.title_label.pack(side="left", pady=spacing.sm)

        self.header_actions = tk.Frame(self.header, bg=V2_HEADER_BG)
        self.header_actions.pack(side="right", padx=spacing.sm, pady=spacing.sm)

        self.body = tk.Frame(self, bg=V2_BG)
        self.body.pack(fill="both", expand=True, padx=spacing.lg, pady=(0, spacing.sm))

        self.nav = tk.Frame(self.body, bg=V2_NAV_BG, width=180)
        self.nav.pack(side="left", fill="y")
        self.nav.pack_propagate(False)

        self.workspace = tk.Frame(self.body, bg=V2_PANEL)
        self.workspace.pack(side="left", fill="both", expand=True, padx=(spacing.md, spacing.md))

        self.inspector = tk.Frame(self.body, bg=V2_INSPECTOR_BG, width=240)
        self.inspector.pack(side="right", fill="y")
        self.inspector.pack_propagate(False)

        self.inspector_title = tk.Label(
            self.inspector,
            text="Inspector",
            bg=V2_INSPECTOR_BG,
            fg=colors.text_primary,
            font=type_scale.section_title,
        )
        self.inspector_title.pack(anchor="w", padx=spacing.md, pady=(spacing.md, spacing.xs))

        self.inspector_text = tk.Label(
            self.inspector,
            text="Select a section to view details.",
            bg=V2_INSPECTOR_BG,
            fg=colors.text_primary,
            justify="left",
            anchor="nw",
            wraplength=220,
            font=type_scale.body_small,
        )
        self.inspector_text.pack(fill="both", expand=True, padx=spacing.md, pady=(0, spacing.md))

        self.status_var = tk.StringVar(value="Ready.")
        self.status_strip = tk.Label(
            self,
            textvariable=self.status_var,
            anchor="w",
            bg=colors.status_bg,
            fg=colors.status_fg,
            padx=spacing.lg,
            pady=spacing.sm - spacing.xs,
            font=type_scale.body_bold,
        )
        self.status_strip.pack(fill="x", padx=spacing.lg, pady=(0, spacing.lg))

    def add_header_action(self, text: str, command) -> tk.Button:
        spacing = V2_THEME.spacing
        button = tk.Button(
            self.header_actions,
            text=text,
            command=command,
            padx=spacing.md,
            pady=spacing.sm - spacing.xs,
            **v2_button_options("secondary"),
        )
        button.pack(side="right", padx=(spacing.sm, 0))
        return button

    def add_nav_button(self, key: str, text: str, command) -> tk.Button:
        spacing = V2_THEME.spacing
        button = tk.Button(
            self.nav,
            text=text,
            command=command,
            anchor="w",
            padx=spacing.lg + spacing.xs,
            pady=spacing.md,
            **v2_button_options("nav"),
        )
        button.pack(fill="x", pady=(spacing.xxs, 0))
        self._nav_buttons[key] = button
        return button

    def set_nav_active(self, key: str) -> None:
        colors = V2_THEME.colors
        active_found = False
        for button_key, button in self._nav_buttons.items():
            if button_key == key:
                button.configure(
                    bg=colors.nav_active_bg,
                    fg=colors.nav_active_fg,
                    activebackground=colors.nav_active_bg,
                    activeforeground=colors.nav_active_fg,
                )
                active_found = True
            else:
                button.configure(
                    bg=colors.nav_bg,
                    fg=colors.nav_fg,
                    activebackground=colors.nav_active_bg,
                    activeforeground=colors.nav_active_fg,
                )
        if active_found:
            self._active_nav_key = key

    @property
    def active_nav_key(self) -> str | None:
        return self._active_nav_key

    def set_status(self, text: str) -> None:
        self.status_var.set(text)

    def set_inspector(self, title: str, lines: list[str]) -> None:
        self.inspector_title.configure(text=title)
        if not lines:
            self.inspector_text.configure(text="No details.")
            return
        self.inspector_text.configure(text="\n".join(f"- {line}" for line in lines))



__all__ = ["V2ShellFrame"]
