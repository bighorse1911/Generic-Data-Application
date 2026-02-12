"""Theme helpers for gui_kit screens."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

DARK_BG = "#1e1f22"
DARK_SURFACE = "#2a2d33"
DARK_FIELD = "#2f3239"
DARK_BORDER = "#3d414a"
DARK_TEXT = "#f2f3f5"
DARK_MUTED = "#c8ccd4"
DARK_ACCENT = "#6aa5ff"
DARK_ACCENT_ACTIVE = "#8db9ff"


def apply_dark_mode(root: tk.Misc, widget_root: tk.Misc | None = None) -> None:
    """Apply a dark ttk theme and style tk widgets under widget_root."""

    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    style.configure(".", background=DARK_BG, foreground=DARK_TEXT)
    style.configure("TFrame", background=DARK_BG)
    style.configure("TLabel", background=DARK_BG, foreground=DARK_TEXT)
    style.configure(
        "TButton",
        background=DARK_SURFACE,
        foreground=DARK_TEXT,
        bordercolor=DARK_BORDER,
        lightcolor=DARK_BORDER,
        darkcolor=DARK_BORDER,
    )
    style.map(
        "TButton",
        background=[("active", DARK_ACCENT), ("pressed", DARK_ACCENT_ACTIVE)],
        foreground=[("disabled", DARK_MUTED)],
    )
    style.configure("TCheckbutton", background=DARK_BG, foreground=DARK_TEXT)
    style.configure("TEntry", fieldbackground=DARK_FIELD, foreground=DARK_TEXT)
    style.configure("TCombobox", fieldbackground=DARK_FIELD, foreground=DARK_TEXT)
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", DARK_FIELD)],
        foreground=[("readonly", DARK_TEXT)],
    )
    style.configure(
        "TLabelframe",
        background=DARK_BG,
        foreground=DARK_TEXT,
        bordercolor=DARK_BORDER,
        lightcolor=DARK_BORDER,
        darkcolor=DARK_BORDER,
    )
    style.configure("TLabelframe.Label", background=DARK_BG, foreground=DARK_TEXT)
    style.configure("TNotebook", background=DARK_BG, bordercolor=DARK_BORDER)
    style.configure("TNotebook.Tab", background=DARK_SURFACE, foreground=DARK_TEXT, padding=(10, 4))
    style.map(
        "TNotebook.Tab",
        background=[("selected", DARK_ACCENT), ("active", DARK_ACCENT_ACTIVE)],
        foreground=[("selected", DARK_BG)],
    )
    style.configure(
        "Treeview",
        background=DARK_FIELD,
        fieldbackground=DARK_FIELD,
        foreground=DARK_TEXT,
    )
    style.map(
        "Treeview",
        background=[("selected", DARK_ACCENT)],
        foreground=[("selected", DARK_BG)],
    )
    style.configure(
        "Treeview.Heading",
        background=DARK_SURFACE,
        foreground=DARK_TEXT,
        bordercolor=DARK_BORDER,
    )
    style.map("Treeview.Heading", background=[("active", DARK_ACCENT_ACTIVE)])

    toplevel = root.winfo_toplevel() if hasattr(root, "winfo_toplevel") else None
    if isinstance(toplevel, (tk.Tk, tk.Toplevel)):
        toplevel.configure(bg=DARK_BG)

    if widget_root is None:
        widget_root = root
    _apply_tk_widget_colors(widget_root)


def _apply_tk_widget_colors(widget: tk.Misc) -> None:
    for child in widget.winfo_children():
        if isinstance(child, tk.Listbox):
            child.configure(
                bg=DARK_FIELD,
                fg=DARK_TEXT,
                selectbackground=DARK_ACCENT,
                selectforeground=DARK_BG,
                highlightbackground=DARK_BORDER,
                highlightcolor=DARK_ACCENT,
                relief="flat",
            )
        elif isinstance(child, tk.Canvas):
            child.configure(bg=DARK_BG)

        _apply_tk_widget_colors(child)
