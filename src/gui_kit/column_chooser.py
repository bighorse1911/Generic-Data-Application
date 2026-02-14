"""Dialog helpers for choosing table/preview column visibility and display order."""

from __future__ import annotations

from collections.abc import Callable
import tkinter as tk
from tkinter import messagebox, ttk

__all__ = ["ColumnChooserDialog", "normalize_column_preferences"]


def normalize_column_preferences(
    columns: list[str],
    visible_columns: list[str] | None = None,
) -> list[tuple[str, bool]]:
    """
    Normalize columns + visibility into ordered (column, visible) tuples.

    - Preserves canonical column order for any columns not explicitly reordered.
    - Filters out unknown visible columns.
    """

    canonical: list[str] = []
    seen: set[str] = set()
    for name in columns:
        value = str(name).strip()
        if value == "" or value in seen:
            continue
        canonical.append(value)
        seen.add(value)

    if not canonical:
        return []

    if visible_columns is None:
        return [(name, True) for name in canonical]

    visible_order: list[str] = []
    for name in visible_columns:
        value = str(name).strip()
        if value in seen and value not in visible_order:
            visible_order.append(value)

    ordered = list(visible_order)
    ordered.extend([name for name in canonical if name not in visible_order])
    visible_set = set(visible_order)
    return [(name, name in visible_set) for name in ordered]


class ColumnChooserDialog(tk.Toplevel):
    """Modal dialog that edits visible-column selection and display order."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        columns: list[str],
        visible_columns: list[str] | None = None,
        on_apply: Callable[[list[str]], None],
        title: str = "Choose visible columns",
    ) -> None:
        super().__init__(parent)
        self._on_apply = on_apply
        self._rows = normalize_column_preferences(columns, visible_columns)

        self.title(title)
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.geometry("520x420")

        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        ttk.Label(
            root,
            text=(
                "Use Toggle + Move Up/Down to choose visible columns and display order. "
                "Underlying schema column order is unchanged."
            ),
            justify="left",
            wraplength=480,
        ).grid(row=0, column=0, sticky="w")

        body = ttk.Frame(root)
        body.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        self.listbox = tk.Listbox(body, exportselection=False, activestyle="none")
        self.listbox.grid(row=0, column=0, sticky="nsew")
        y_scroll = ttk.Scrollbar(body, orient="vertical", command=self.listbox.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=y_scroll.set)

        controls = ttk.Frame(root)
        controls.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(2, weight=1)
        controls.columnconfigure(3, weight=1)

        ttk.Button(controls, text="Toggle visible", command=self._toggle_selected).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        ttk.Button(controls, text="Move up", command=lambda: self._move_selected(-1)).grid(
            row=0, column=1, sticky="ew", padx=4
        )
        ttk.Button(controls, text="Move down", command=lambda: self._move_selected(1)).grid(
            row=0, column=2, sticky="ew", padx=4
        )
        ttk.Button(controls, text="Show all", command=lambda: self._set_all_visible(True)).grid(
            row=0, column=3, sticky="ew", padx=(4, 0)
        )

        actions = ttk.Frame(root)
        actions.grid(row=3, column=0, sticky="e", pady=(10, 0))
        ttk.Button(actions, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(actions, text="Apply", command=self._on_apply_clicked).pack(side="right", padx=(0, 8))

        self.listbox.bind("<Double-1>", lambda _e: self._toggle_selected())
        self.listbox.bind("<Return>", lambda _e: self._toggle_selected())

        self._render()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.focus_set()

    def _render(self) -> None:
        selected = self._selected_index()
        self.listbox.delete(0, tk.END)
        for name, visible in self._rows:
            marker = "[x]" if visible else "[ ]"
            self.listbox.insert(tk.END, f"{marker} {name}")
        if selected is not None and 0 <= selected < len(self._rows):
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(selected)
            self.listbox.activate(selected)

    def _selected_index(self) -> int | None:
        sel = self.listbox.curselection()
        if not sel:
            return None
        return int(sel[0])

    def _toggle_selected(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        name, visible = self._rows[index]
        self._rows[index] = (name, not visible)
        self._render()

    def _move_selected(self, delta: int) -> None:
        index = self._selected_index()
        if index is None:
            return
        target = index + delta
        if target < 0 or target >= len(self._rows):
            return
        self._rows[index], self._rows[target] = self._rows[target], self._rows[index]
        self._render()
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(target)
        self.listbox.activate(target)
        self.listbox.see(target)

    def _set_all_visible(self, visible: bool) -> None:
        self._rows = [(name, visible) for name, _ in self._rows]
        self._render()

    def _on_apply_clicked(self) -> None:
        selected = [name for name, visible in self._rows if visible]
        if not selected:
            messagebox.showerror(
                "Column chooser",
                "Column chooser: at least one visible column is required. "
                "Fix: toggle one or more columns to visible before applying.",
            )
            return
        self._on_apply(selected)
        self.destroy()
