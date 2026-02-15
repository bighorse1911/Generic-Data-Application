"""Keyboard ergonomics helpers for Treeview-backed tables."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

__all__ = ["copy_treeview_selection_as_tsv", "install_treeview_keyboard_support"]


def _treeview_rows_for_copy(tree: ttk.Treeview) -> tuple[list[str], list[str]]:
    columns = [str(name) for name in tree["columns"]]
    selection = list(tree.selection())
    if not selection:
        focused = tree.focus()
        if focused:
            selection = [focused]
    rows: list[str] = []
    for item_id in selection:
        values = tree.item(item_id, "values")
        row_values = [str(value) for value in values]
        rows.append("\t".join(row_values))
    return columns, rows


def copy_treeview_selection_as_tsv(tree: ttk.Treeview, *, include_headers: bool = True) -> str:
    columns, rows = _treeview_rows_for_copy(tree)
    if not rows:
        return ""
    parts: list[str] = []
    if include_headers and columns:
        parts.append("\t".join(columns))
    parts.extend(rows)
    text = "\n".join(parts)
    top = tree.winfo_toplevel()
    top.clipboard_clear()
    top.clipboard_append(text)
    top.update_idletasks()
    return text


def _ensure_selection(tree: ttk.Treeview, *, prefer_last: bool) -> bool:
    children = list(tree.get_children(""))
    if not children:
        return False
    if tree.selection():
        return False
    target = children[-1] if prefer_last else children[0]
    tree.selection_set(target)
    tree.focus(target)
    tree.see(target)
    return True


def install_treeview_keyboard_support(
    tree: ttk.Treeview,
    *,
    include_headers: bool = True,
) -> None:
    """Install row-copy and no-selection recovery handlers on a Treeview."""

    def _copy(_event=None) -> str:
        copied = copy_treeview_selection_as_tsv(tree, include_headers=include_headers)
        return "break" if copied else "break"

    def _on_up(_event=None) -> str | None:
        if _ensure_selection(tree, prefer_last=False):
            return "break"
        return None

    def _on_down(_event=None) -> str | None:
        if _ensure_selection(tree, prefer_last=False):
            return "break"
        return None

    def _on_home(_event=None) -> str | None:
        if _ensure_selection(tree, prefer_last=False):
            return "break"
        return None

    def _on_end(_event=None) -> str | None:
        if _ensure_selection(tree, prefer_last=True):
            return "break"
        return None

    tree.bind("<Control-c>", _copy, add="+")
    tree.bind("<Command-c>", _copy, add="+")
    tree.bind("<Control-C>", _copy, add="+")
    tree.bind("<Command-C>", _copy, add="+")
    tree.bind("<Up>", _on_up, add="+")
    tree.bind("<Down>", _on_down, add="+")
    tree.bind("<Home>", _on_home, add="+")
    tree.bind("<End>", _on_end, add="+")
