"""Non-blocking feedback helpers for Tkinter screens."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

__all__ = ["ToastCenter"]


_TOAST_COLORS: dict[str, str] = {
    "info": "#d9ecff",
    "success": "#dff5e1",
    "warn": "#fff4cf",
    "error": "#ffd9d9",
}


class ToastCenter(ttk.Frame):
    """Stacked non-blocking toast notifications."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        default_duration_ms: int = 2500,
        max_toasts: int = 4,
    ) -> None:
        super().__init__(parent)
        self.default_duration_ms = max(250, int(default_duration_ms))
        self.max_toasts = max(1, int(max_toasts))
        self._cards: list[tk.Frame] = []
        self.columnconfigure(0, weight=1)

        # Float in the top-right corner of the owning screen.
        self.place(in_=parent, relx=1.0, x=-12, y=12, anchor="ne")

    def show_toast(
        self,
        message: str,
        *,
        level: str = "info",
        duration_ms: int | None = None,
    ) -> None:
        text = message.strip()
        if text == "":
            return

        color = _TOAST_COLORS.get(level, _TOAST_COLORS["info"])
        card = tk.Frame(self, bg=color, bd=1, relief="solid")
        label = tk.Label(
            card,
            text=text,
            bg=color,
            justify="left",
            anchor="w",
            wraplength=360,
            padx=8,
            pady=6,
        )
        label.pack(fill="x")
        card.grid(row=len(self._cards), column=0, sticky="ew", pady=(0, 6))
        self._cards.append(card)
        self._trim()

        timeout = self.default_duration_ms if duration_ms is None else max(250, int(duration_ms))
        self.after(timeout, lambda c=card: self.dismiss_toast(c))

    def dismiss_toast(self, card: tk.Frame) -> None:
        if card not in self._cards:
            return
        self._cards.remove(card)
        try:
            card.destroy()
        except tk.TclError:
            return
        self._reflow()

    def _trim(self) -> None:
        while len(self._cards) > self.max_toasts:
            oldest = self._cards[0]
            self.dismiss_toast(oldest)

    def _reflow(self) -> None:
        for row, card in enumerate(self._cards):
            if card.winfo_exists():
                card.grid_configure(row=row)
