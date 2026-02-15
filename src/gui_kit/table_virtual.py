from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk

from src.gui_kit.table import TableView

__all__ = ["TableColumnSpec", "VirtualTableAdapter"]


@dataclass(frozen=True)
class TableColumnSpec:
    key: str
    heading: str
    width: int = 120
    anchor: str = "w"
    stretch: bool = False


class VirtualTableAdapter:
    """Table adapter with consistent configuration and optional pagination."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        columns: list[TableColumnSpec],
        height: int = 8,
        page_size: int | None = None,
    ) -> None:
        self.view = TableView(parent, height=height)
        self.view.pack(fill="both", expand=True)
        self.columns = list(columns)
        self.view.set_columns([spec.key for spec in self.columns])
        for spec in self.columns:
            self.view.tree.heading(spec.key, text=spec.heading, anchor=spec.anchor)
            self.view.tree.column(spec.key, width=spec.width, anchor=spec.anchor, stretch=spec.stretch)
        if page_size is not None:
            self.view.enable_pagination(page_size=page_size)

    @property
    def tree(self) -> ttk.Treeview:
        return self.view.tree

    def set_rows(self, rows: list[dict[str, object]] | list[list[object]] | list[tuple[object, ...]]) -> None:
        self.view.set_rows(rows)

    def clear(self) -> None:
        self.view.clear()

    def enable_pagination(self, *, page_size: int = 200) -> None:
        self.view.enable_pagination(page_size=page_size)

    def disable_pagination(self) -> None:
        self.view.disable_pagination()
