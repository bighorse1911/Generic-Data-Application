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
        large_data_enabled: bool = False,
        large_data_threshold_rows: int = 1000,
        large_data_chunk_size: int = 200,
        large_data_auto_pagination: bool = False,
        large_data_auto_page_size: int = 200,
    ) -> None:
        self.view = TableView(parent, height=height)
        self.view.pack(fill="both", expand=True)
        self.columns = list(columns)
        self.view.configure_large_data_mode(
            enabled=large_data_enabled,
            threshold_rows=large_data_threshold_rows,
            chunk_size=large_data_chunk_size,
            auto_pagination=large_data_auto_pagination,
            auto_page_size=large_data_auto_page_size,
        )
        self.view.set_columns([spec.key for spec in self.columns])
        for spec in self.columns:
            self.view.tree.heading(spec.key, text=spec.heading, anchor=spec.anchor)
            self.view.tree.column(spec.key, width=spec.width, anchor=spec.anchor, stretch=spec.stretch)
        if page_size is not None:
            self.view.enable_pagination(page_size=page_size)

    @property
    def tree(self) -> ttk.Treeview:
        return self.view.tree

    @property
    def is_rendering(self) -> bool:
        return self.view.is_rendering

    def set_rows(
        self,
        rows: list[dict[str, object]] | list[list[object]] | list[tuple[object, ...]],
        *,
        non_blocking: bool | None = None,
    ) -> None:
        self.view.set_rows(rows, non_blocking=non_blocking)

    def clear(self) -> None:
        self.view.clear()

    def enable_pagination(self, *, page_size: int = 200) -> None:
        self.view.enable_pagination(page_size=page_size)

    def disable_pagination(self) -> None:
        self.view.disable_pagination()

    def configure_large_data_mode(
        self,
        *,
        enabled: bool,
        threshold_rows: int = 1000,
        chunk_size: int = 200,
        auto_pagination: bool = False,
        auto_page_size: int = 200,
    ) -> None:
        self.view.configure_large_data_mode(
            enabled=enabled,
            threshold_rows=threshold_rows,
            chunk_size=chunk_size,
            auto_pagination=auto_pagination,
            auto_page_size=auto_page_size,
        )

    def cancel_pending_render(self) -> None:
        self.view.cancel_pending_render()
