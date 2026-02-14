"""Search field with deterministic debounce behavior."""

from __future__ import annotations

from collections.abc import Callable
import tkinter as tk
from tkinter import ttk

__all__ = ["SearchEntry"]


class SearchEntry(ttk.Frame):
    """Search control with fixed debounce delay and clear action."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        on_change: Callable[[str], None],
        delay_ms: int = 180,
    ) -> None:
        super().__init__(parent)
        self._on_change = on_change
        self._delay_ms = max(0, int(delay_ms))
        self._pending_after_id: str | None = None
        self.query_var = tk.StringVar(value="")

        self.columnconfigure(0, weight=1)

        self.entry = ttk.Entry(self, textvariable=self.query_var)
        self.entry.grid(row=0, column=0, sticky="ew")
        self.clear_btn = ttk.Button(self, text="Clear", width=6, command=self.clear)
        self.clear_btn.grid(row=0, column=1, padx=(6, 0))

        self.query_var.trace_add("write", self._on_query_changed)

    def clear(self) -> None:
        self.query_var.set("")

    def focus(self) -> None:
        self.entry.focus_set()

    def _on_query_changed(self, *_args) -> None:
        if self._pending_after_id is not None:
            self.after_cancel(self._pending_after_id)
            self._pending_after_id = None
        self._pending_after_id = self.after(self._delay_ms, self._emit_now)

    def _emit_now(self) -> None:
        self._pending_after_id = None
        self._on_change(self.query_var.get())
