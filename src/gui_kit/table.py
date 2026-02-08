from collections.abc import Sequence
import tkinter as tk
from tkinter import ttk


def normalize_rows(
    rows: list[dict[str, object]] | list[list[object]] | list[tuple[object, ...]],
    columns: list[str] | None = None,
) -> tuple[list[str], list[list[object]]]:
    if not rows:
        return (columns or []), []

    first = rows[0]
    if isinstance(first, dict):
        out_cols = columns or list(first.keys())
        normalized: list[list[object]] = []
        for row in rows:
            assert isinstance(row, dict)
            normalized.append([row.get(col, "") for col in out_cols])
        return out_cols, normalized

    out_rows: list[list[object]] = []
    max_len = 0
    for row in rows:
        if isinstance(row, Sequence) and not isinstance(row, (str, bytes)):
            values = list(row)
        else:
            values = [row]
        out_rows.append(values)
        max_len = max(max_len, len(values))

    out_cols = columns or [f"col_{idx + 1}" for idx in range(max_len)]

    padded_rows: list[list[object]] = []
    target_width = len(out_cols)
    for values in out_rows:
        padded = list(values[:target_width])
        if len(padded) < target_width:
            padded.extend([""] * (target_width - len(padded)))
        padded_rows.append(padded)
    return out_cols, padded_rows


def estimate_column_widths(
    columns: list[str],
    rows: list[list[object]],
    *,
    min_px: int = 80,
    max_px: int = 320,
    pad_px: int = 24,
    char_px: int = 7,
) -> dict[str, int]:
    widths: dict[str, int] = {}
    for col_idx, col in enumerate(columns):
        longest = len(col)
        for row in rows:
            if col_idx >= len(row):
                continue
            text = "" if row[col_idx] is None else str(row[col_idx])
            longest = max(longest, len(text))
        px = longest * char_px + pad_px
        widths[col] = max(min_px, min(max_px, px))
    return widths


class TableView(ttk.Frame):
    """
    Treeview wrapper with horizontal + vertical scrollbars and convenience APIs.
    """

    def __init__(self, parent: tk.Widget, *, height: int = 8) -> None:
        super().__init__(parent)

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(self, show="headings", height=height)
        self.v_scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.h_scroll = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=self.v_scroll.set, xscrollcommand=self.h_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.h_scroll.grid(row=1, column=0, sticky="ew")

        self._columns: list[str] = []

    def set_columns(self, columns: list[str]) -> None:
        self._columns = list(columns)
        self.tree["columns"] = tuple(self._columns)
        for col in self._columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120, anchor="w", stretch=True)

    def clear(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

    def set_rows(
        self,
        rows: list[dict[str, object]] | list[list[object]] | list[tuple[object, ...]],
    ) -> None:
        cols, normalized = normalize_rows(rows, self._columns or None)
        if not self._columns and cols:
            self.set_columns(cols)

        self.clear()
        for values in normalized:
            self.tree.insert("", tk.END, values=values)

        if self._columns:
            self.auto_size_columns(normalized)

    def auto_size_columns(self, normalized_rows: list[list[object]] | None = None) -> None:
        if not self._columns:
            return

        rows = normalized_rows or []
        widths = estimate_column_widths(self._columns, rows)
        for col, width in widths.items():
            self.tree.column(col, width=width)
