import tkinter as tk
from tkinter import ttk


class CollapsiblePanel(ttk.Frame):
    """
    Collapsible section container.

    Pack the panel as a top-level section, and use grid inside `body`.
    """

    def __init__(self, parent: tk.Widget, title: str, *, collapsed: bool = False) -> None:
        super().__init__(parent)
        self._collapsed = collapsed

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.header = ttk.Frame(self)
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.columnconfigure(1, weight=1)

        self.toggle_button = ttk.Button(self.header, width=2, command=self.toggle)
        self.toggle_button.grid(row=0, column=0, sticky="w")

        self.title_label = ttk.Label(self.header, text=title, font=("Segoe UI", 10, "bold"))
        self.title_label.grid(row=0, column=1, sticky="w", padx=(6, 0))

        self.title_label.bind("<Button-1>", self._on_header_click)
        self.header.bind("<Button-1>", self._on_header_click)

        self.body = ttk.Frame(self)
        self.body.grid(row=1, column=0, sticky="nsew", pady=(6, 0))

        if self._collapsed:
            self.body.grid_remove()
        self._sync_toggle_text()

    def _on_header_click(self, _event=None) -> None:
        self.toggle()

    def _sync_toggle_text(self) -> None:
        self.toggle_button.configure(text="▸" if self._collapsed else "▾")

    def toggle(self) -> None:
        if self._collapsed:
            self.expand()
            return
        self.collapse()

    def collapse(self) -> None:
        if self._collapsed:
            return
        self._collapsed = True
        self.body.grid_remove()
        self._sync_toggle_text()

    def expand(self) -> None:
        if not self._collapsed:
            return
        self._collapsed = False
        self.body.grid()
        self._sync_toggle_text()

    @property
    def is_collapsed(self) -> bool:
        return self._collapsed


class Tabs(ttk.Notebook):
    """Thin wrapper around ttk.Notebook with a convenience add_tab API."""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)

    def add_tab(self, title: str, *, padding: int = 10) -> ttk.Frame:
        frame = ttk.Frame(self, padding=padding)
        self.add(frame, text=title)
        return frame
