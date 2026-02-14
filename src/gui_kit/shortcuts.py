"""Keyboard shortcut registration and discoverable help dialog."""

from __future__ import annotations

from collections.abc import Callable
import tkinter as tk
from tkinter import ttk

__all__ = ["ShortcutManager"]


class ShortcutManager:
    """Centralized shortcut registration with a built-in help dialog."""

    def __init__(self, widget: tk.Widget) -> None:
        self.widget = widget
        self._items: list[tuple[str, str, Callable[[], None]]] = []
        self._help_dialog: tk.Toplevel | None = None

    def register(self, sequence: str, description: str, callback: Callable[[], None]) -> None:
        seq = sequence.strip()
        desc = description.strip()
        if seq == "" or desc == "":
            raise ValueError(
                "Shortcut manager: sequence and description are required. "
                "Fix: provide non-empty shortcut sequence and description."
            )

        def _wrapped(_event=None):
            callback()
            return "break"

        self.widget.bind_all(seq, _wrapped, add="+")
        self._items.append((seq, desc, callback))

    def items(self) -> list[tuple[str, str]]:
        return [(seq, desc) for (seq, desc, _cb) in self._items]

    def show_help_dialog(self, *, title: str = "Keyboard shortcuts") -> None:
        if self._help_dialog is not None and self._help_dialog.winfo_exists():
            self._help_dialog.lift()
            self._help_dialog.focus_force()
            return

        top = tk.Toplevel(self.widget)
        self._help_dialog = top
        top.title(title)
        top.transient(self.widget.winfo_toplevel())
        top.geometry("520x300")

        body = ttk.Frame(top, padding=12)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        tree = ttk.Treeview(body, columns=("shortcut", "action"), show="headings", height=10)
        tree.heading("shortcut", text="Shortcut")
        tree.heading("action", text="Action")
        tree.column("shortcut", width=160, anchor="w")
        tree.column("action", width=320, anchor="w")
        tree.grid(row=0, column=0, sticky="nsew")

        y_scroll = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=y_scroll.set)
        y_scroll.grid(row=0, column=1, sticky="ns")

        for seq, desc in self.items():
            tree.insert("", tk.END, values=(seq, desc))

        close_btn = ttk.Button(body, text="Close", command=top.destroy)
        close_btn.grid(row=1, column=0, sticky="e", pady=(10, 0))
