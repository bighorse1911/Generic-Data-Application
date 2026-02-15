"""Keyboard shortcut registration and discoverable help dialog."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk

__all__ = ["ShortcutManager"]


@dataclass(frozen=True)
class _ShortcutSpec:
    sequences: tuple[str, ...]
    description: str
    callback: Callable[[], None]


class ShortcutManager:
    """Centralized, route-scoped shortcut registration with a help dialog."""

    def __init__(self, widget: tk.Widget) -> None:
        self.widget = widget
        self._items: list[_ShortcutSpec] = []
        self._help_dialog: tk.Toplevel | None = None
        self._active = False
        self._bound_root: tk.Misc | None = None
        self._bound_ids: dict[str, list[str]] = {}

    def register(
        self,
        sequence: str,
        description: str,
        callback: Callable[[], None],
        *,
        aliases: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        seq = sequence.strip()
        desc = description.strip()
        if seq == "" or desc == "":
            raise ValueError(
                "Shortcut manager: sequence and description are required. "
                "Fix: provide non-empty shortcut sequence and description."
            )
        sequence_list = [seq]
        if aliases:
            for alias in aliases:
                alias_seq = str(alias).strip()
                if alias_seq and alias_seq not in sequence_list:
                    sequence_list.append(alias_seq)
        self._items.append(_ShortcutSpec(tuple(sequence_list), desc, callback))
        if self._active:
            self._bind_spec(self._items[-1])

    def register_ctrl_cmd(
        self,
        key: str,
        description: str,
        callback: Callable[[], None],
        *,
        shift: bool = False,
    ) -> None:
        key_token = str(key).strip()
        if key_token == "":
            raise ValueError(
                "Shortcut manager: key token is required for register_ctrl_cmd. "
                "Fix: provide a non-empty key token such as 's' or 'Return'."
            )
        shift_prefix = "Shift-" if shift else ""
        primary = f"<Control-{shift_prefix}{key_token}>"
        alias = f"<Command-{shift_prefix}{key_token}>"
        self.register(primary, description, callback, aliases=[alias])

    def activate(self) -> None:
        if self._active:
            return
        root = self.widget.winfo_toplevel()
        self._bound_root = root
        self._active = True
        self._bound_ids.clear()
        for spec in self._items:
            self._bind_spec(spec)

    def deactivate(self) -> None:
        if not self._active:
            return
        root = self._bound_root
        if root is not None:
            for sequence, bind_ids in list(self._bound_ids.items()):
                for bind_id in bind_ids:
                    root.unbind(sequence, bind_id)
        self._bound_ids.clear()
        self._bound_root = None
        self._active = False

    def _bind_spec(self, spec: _ShortcutSpec) -> None:
        if not self._active or self._bound_root is None:
            return
        root = self._bound_root
        for sequence in spec.sequences:
            def _wrapped(_event=None, callback=spec.callback):
                callback()
                return "break"

            bind_id = root.bind(sequence, _wrapped, add="+")
            if bind_id:
                self._bound_ids.setdefault(sequence, []).append(bind_id)

    def items(self) -> list[tuple[str, str]]:
        return [(spec.sequences[0], spec.description) for spec in self._items]

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
