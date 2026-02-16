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


def _select_item(tree: ttk.Treeview, item_id: str) -> None:
    tree.selection_set(item_id)
    tree.focus(item_id)
    tree.see(item_id)


def _page_step_size(tree: ttk.Treeview) -> int:
    try:
        raw = int(tree.cget("height"))
    except (TypeError, ValueError, tk.TclError):
        raw = 10
    return max(1, raw - 1)


def install_treeview_keyboard_support(
    tree: ttk.Treeview,
    *,
    include_headers: bool = True,
) -> None:
    """Install row-copy and no-selection recovery handlers on a Treeview."""

    def _copy(*, include_headers_value: bool, _event=None) -> str:
        copied = copy_treeview_selection_as_tsv(tree, include_headers=include_headers_value)
        return "break" if copied else "break"

    def _select_all(_event=None) -> str:
        children = list(tree.get_children(""))
        if not children:
            return "break"
        tree.selection_set(children)
        tree.focus(children[0])
        tree.see(children[0])
        return "break"

    def _move_by_pages(*, page_delta: int) -> str | None:
        children = list(tree.get_children(""))
        if not children:
            return "break"
        if _ensure_selection(tree, prefer_last=(page_delta < 0)):
            return "break"
        focused = tree.focus()
        selection = list(tree.selection())
        current = focused if focused in children else (selection[0] if selection else children[0])
        current_idx = children.index(current)
        step = _page_step_size(tree)
        target_idx = max(0, min(len(children) - 1, current_idx + (step * page_delta)))
        _select_item(tree, children[target_idx])
        return "break"

    def _jump_endpoint(*, prefer_last: bool) -> str:
        children = list(tree.get_children(""))
        if not children:
            return "break"
        target = children[-1] if prefer_last else children[0]
        _select_item(tree, target)
        return "break"

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

    tree.bind("<Control-c>", lambda event: _copy(include_headers_value=include_headers, _event=event), add="+")
    tree.bind("<Command-c>", lambda event: _copy(include_headers_value=include_headers, _event=event), add="+")
    tree.bind("<Control-C>", lambda event: _copy(include_headers_value=include_headers, _event=event), add="+")
    tree.bind("<Command-C>", lambda event: _copy(include_headers_value=include_headers, _event=event), add="+")
    tree.bind("<Control-Shift-C>", lambda event: _copy(include_headers_value=False, _event=event), add="+")
    tree.bind("<Command-Shift-C>", lambda event: _copy(include_headers_value=False, _event=event), add="+")
    tree.bind("<Control-Shift-c>", lambda event: _copy(include_headers_value=False, _event=event), add="+")
    tree.bind("<Command-Shift-c>", lambda event: _copy(include_headers_value=False, _event=event), add="+")
    tree.bind("<Control-a>", _select_all, add="+")
    tree.bind("<Command-a>", _select_all, add="+")
    tree.bind("<Control-A>", _select_all, add="+")
    tree.bind("<Command-A>", _select_all, add="+")
    tree.bind("<Up>", _on_up, add="+")
    tree.bind("<Down>", _on_down, add="+")
    tree.bind("<Home>", _on_home, add="+")
    tree.bind("<End>", _on_end, add="+")
    tree.bind("<Prior>", lambda _event=None: _move_by_pages(page_delta=-1), add="+")
    tree.bind("<Next>", lambda _event=None: _move_by_pages(page_delta=1), add="+")
    tree.bind("<Page_Up>", lambda _event=None: _move_by_pages(page_delta=-1), add="+")
    tree.bind("<Page_Down>", lambda _event=None: _move_by_pages(page_delta=1), add="+")
    tree.bind("<Control-Home>", lambda _event=None: _jump_endpoint(prefer_last=False), add="+")
    tree.bind("<Command-Home>", lambda _event=None: _jump_endpoint(prefer_last=False), add="+")
    tree.bind("<Control-End>", lambda _event=None: _jump_endpoint(prefer_last=True), add="+")
    tree.bind("<Command-End>", lambda _event=None: _jump_endpoint(prefer_last=True), add="+")
