"""Table helpers and a Treeview wrapper with predictable row handling."""

from collections.abc import Sequence
import tkinter as tk
from tkinter import ttk

from src.gui_kit.table_keyboard import install_treeview_keyboard_support

__all__ = ["TableView", "estimate_column_widths", "normalize_rows", "paginate_rows"]


def normalize_rows(
    rows: list[dict[str, object]] | list[list[object]] | list[tuple[object, ...]],
    columns: list[str] | None = None,
) -> tuple[list[str], list[list[object]]]:
    """Normalize dict/sequence/scalar rows to a (columns, rows) table shape."""

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
    """Estimate column widths in pixels from headers and sample rows."""

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


def paginate_rows(
    rows: list[list[object]],
    *,
    page_size: int,
    page_index: int,
) -> tuple[list[list[object]], int, int]:
    """
    Return one page of rows with normalized page index metadata.

    Returns:
    - page_rows
    - normalized_page_index (0-based)
    - total_pages
    """

    if page_size <= 0:
        raise ValueError(
            "TableView pagination: page_size must be > 0. "
            "Fix: set a positive page size."
        )

    total_rows = len(rows)
    if total_rows == 0:
        return [], 0, 0

    total_pages = (total_rows + page_size - 1) // page_size
    normalized_index = min(max(0, page_index), total_pages - 1)
    start = normalized_index * page_size
    end = min(total_rows, start + page_size)
    return rows[start:end], normalized_index, total_pages


class TableView(ttk.Frame):
    """
    Treeview wrapper with horizontal + vertical scrollbars and convenience APIs.
    """

    def __init__(self, parent: tk.Widget, *, height: int = 8) -> None:
        super().__init__(parent)

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(self, show="headings", height=height)
        install_treeview_keyboard_support(self.tree, include_headers=True)
        self.v_scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.h_scroll = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=self.v_scroll.set, xscrollcommand=self.h_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.h_scroll.grid(row=1, column=0, sticky="ew")

        self._columns: list[str] = []
        self._all_rows: list[list[object]] = []
        self._pagination_enabled = False
        self._page_size = 200
        self._page_index = 0

        self.pagination_bar = ttk.Frame(self)
        self.pagination_bar.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.pagination_bar.columnconfigure(1, weight=1)
        self.prev_btn = ttk.Button(self.pagination_bar, text="Prev", width=6, command=self.previous_page)
        self.prev_btn.grid(row=0, column=0, sticky="w")
        self.page_var = tk.StringVar(value="")
        ttk.Label(self.pagination_bar, textvariable=self.page_var).grid(row=0, column=1, sticky="w", padx=(8, 8))
        self.next_btn = ttk.Button(self.pagination_bar, text="Next", width=6, command=self.next_page)
        self.next_btn.grid(row=0, column=2, sticky="e")
        self.pagination_bar.grid_remove()

    def set_columns(self, columns: list[str]) -> None:
        """Set/replace displayed columns and reset headings/initial widths."""

        self._columns = list(columns)
        self.tree["columns"] = tuple(self._columns)
        for col in self._columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120, anchor="w", stretch=True)

    def clear(self) -> None:
        """Remove all rows from the Treeview."""

        self._all_rows = []
        self._page_index = 0
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._update_page_controls(total_pages=0, start=0, end=0)

    def set_rows(
        self,
        rows: list[dict[str, object]] | list[list[object]] | list[tuple[object, ...]],
    ) -> None:
        """Load rows, normalizing shapes and auto-sizing existing columns."""

        cols, normalized = normalize_rows(rows, self._columns or None)
        if not self._columns and cols:
            self.set_columns(cols)

        self._all_rows = normalized
        self._render_current_rows()

    def auto_size_columns(self, normalized_rows: list[list[object]] | None = None) -> None:
        """Auto-size columns based on current headers and optional row samples."""

        if not self._columns:
            return

        rows = normalized_rows or []
        widths = estimate_column_widths(self._columns, rows)
        for col, width in widths.items():
            self.tree.column(col, width=width)

    @property
    def page_size(self) -> int:
        return self._page_size

    def enable_pagination(self, *, page_size: int = 200) -> None:
        """Enable built-in page controls for large row previews."""

        self.set_page_size(page_size)
        self._pagination_enabled = True
        self.pagination_bar.grid()
        self._render_current_rows()

    def disable_pagination(self) -> None:
        """Disable pagination and render all currently loaded rows."""

        self._pagination_enabled = False
        self._page_index = 0
        self.pagination_bar.grid_remove()
        self._render_current_rows()

    def set_page_size(self, page_size: int) -> None:
        """Set a positive page size and refresh current rows."""

        value = int(page_size)
        if value <= 0:
            raise ValueError(
                "TableView pagination: page_size must be > 0. "
                "Fix: set a positive page size."
            )
        self._page_size = value
        self._page_index = 0
        self._render_current_rows()

    def previous_page(self) -> None:
        if not self._pagination_enabled:
            return
        self._page_index -= 1
        self._render_current_rows()

    def next_page(self) -> None:
        if not self._pagination_enabled:
            return
        self._page_index += 1
        self._render_current_rows()

    def _render_current_rows(self) -> None:
        if self._pagination_enabled:
            page_rows, page_index, total_pages = paginate_rows(
                self._all_rows,
                page_size=self._page_size,
                page_index=self._page_index,
            )
            self._page_index = page_index
            start = 0
            end = 0
            if page_rows:
                start = page_index * self._page_size + 1
                end = start + len(page_rows) - 1
            self._render_rows(page_rows)
            self._update_page_controls(total_pages=total_pages, start=start, end=end)
            return

        self._render_rows(self._all_rows)
        self._update_page_controls(total_pages=0, start=0, end=0)

    def _render_rows(self, rows: list[list[object]]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for values in rows:
            self.tree.insert("", tk.END, values=values)
        if self._columns:
            self.auto_size_columns(rows)

    def _update_page_controls(self, *, total_pages: int, start: int, end: int) -> None:
        if not self._pagination_enabled:
            self.page_var.set("")
            return

        total_rows = len(self._all_rows)
        if total_rows == 0 or total_pages == 0:
            self.page_var.set("No rows.")
            self.prev_btn.configure(state=tk.DISABLED)
            self.next_btn.configure(state=tk.DISABLED)
            return

        self.page_var.set(
            f"Rows {start}-{end} of {total_rows} "
            f"(page {self._page_index + 1}/{total_pages})"
        )
        self.prev_btn.configure(state=(tk.NORMAL if self._page_index > 0 else tk.DISABLED))
        self.next_btn.configure(
            state=(tk.NORMAL if self._page_index + 1 < total_pages else tk.DISABLED)
        )
