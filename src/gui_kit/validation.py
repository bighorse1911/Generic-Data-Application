"""Inline validation summary helpers with jump callbacks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk

__all__ = ["InlineValidationEntry", "InlineValidationSummary"]


@dataclass(frozen=True)
class InlineValidationEntry:
    """One inline validation item rendered by InlineValidationSummary."""

    severity: str
    location: str
    message: str
    jump_payload: object | None = None


class InlineValidationSummary(ttk.Frame):
    """Inline panel listing validation issues with quick-jump actions."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        on_jump: Callable[[InlineValidationEntry], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_jump = on_jump
        self._entry_by_item: dict[str, InlineValidationEntry] = {}
        self.summary_var = tk.StringVar(value="No validation issues.")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        ttk.Label(self, textvariable=self.summary_var).grid(row=0, column=0, sticky="w")

        table_frame = ttk.Frame(self)
        table_frame.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_frame,
            columns=("severity", "location", "message"),
            show="headings",
            height=6,
        )
        self.tree.heading("severity", text="Severity")
        self.tree.heading("location", text="Location")
        self.tree.heading("message", text="Issue")
        self.tree.column("severity", width=90, anchor="w", stretch=False)
        self.tree.column("location", width=180, anchor="w")
        self.tree.column("message", width=540, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")

        y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=y_scroll.set)

        jump_btn = ttk.Button(self, text="Jump to selected issue", command=self.jump_selected)
        jump_btn.grid(row=2, column=0, sticky="e", pady=(8, 0))

        self.tree.bind("<Double-1>", self._on_tree_activate)
        self.tree.bind("<Return>", self._on_tree_activate)

    def set_on_jump(self, callback: Callable[[InlineValidationEntry], None] | None) -> None:
        self._on_jump = callback

    def clear(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._entry_by_item.clear()
        self.summary_var.set("No validation issues.")

    def set_entries(self, entries: list[InlineValidationEntry]) -> None:
        self.clear()
        if not entries:
            return

        for entry in entries:
            item_id = self.tree.insert(
                "",
                tk.END,
                values=(entry.severity.upper(), entry.location, entry.message),
            )
            self._entry_by_item[item_id] = entry

        errors = sum(1 for entry in entries if entry.severity.lower() == "error")
        warnings = sum(1 for entry in entries if entry.severity.lower() == "warn")
        self.summary_var.set(
            f"Inline validation: {errors} errors, {warnings} warnings. "
            "Double-click a row or use Jump to navigate."
        )

    def _on_tree_activate(self, _event=None) -> str:
        self.jump_selected()
        return "break"

    def jump_selected(self) -> None:
        if self._on_jump is None:
            return
        selection = self.tree.selection()
        if not selection:
            return
        item_id = selection[0]
        entry = self._entry_by_item.get(item_id)
        if entry is None:
            return
        self._on_jump(entry)
