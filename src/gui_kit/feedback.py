"""Non-blocking feedback helpers for Tkinter screens."""

from __future__ import annotations

from dataclasses import dataclass
import time
import tkinter as tk
from tkinter import ttk

__all__ = ["NotificationEntry", "NotificationCenter", "ToastCenter"]


_TOAST_COLORS: dict[str, str] = {
    "info": "#d9ecff",
    "success": "#dff5e1",
    "warn": "#fff4cf",
    "error": "#ffd9d9",
}


@dataclass(frozen=True)
class NotificationEntry:
    timestamp: str
    level: str
    message: str


class NotificationCenter(ttk.Frame):
    """Stacked non-blocking notifications with in-memory history."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        default_duration_ms: int = 2500,
        max_toasts: int = 4,
        max_history: int = 300,
    ) -> None:
        super().__init__(parent)
        self.default_duration_ms = max(250, int(default_duration_ms))
        self.max_toasts = max(1, int(max_toasts))
        self.max_history = max(1, int(max_history))
        self._cards: list[tk.Frame] = []
        self._pending_dismiss_after_ids: dict[tk.Frame, str] = {}
        self._history: list[NotificationEntry] = []
        self._history_dialog: tk.Toplevel | None = None
        self._history_tree: ttk.Treeview | None = None
        self.columnconfigure(0, weight=1)
        self.bind("<Destroy>", self._on_destroy, add="+")

        # Float in the top-right corner of the owning screen.
        self.place(in_=parent, relx=1.0, x=-12, y=12, anchor="ne")

    def notify(
        self,
        message: str,
        *,
        level: str = "info",
        duration_ms: int | None = None,
    ) -> None:
        text = message.strip()
        if text == "":
            return

        level_key = str(level).strip().lower() or "info"
        color = _TOAST_COLORS.get(level_key, _TOAST_COLORS["info"])
        self._append_history(level=level_key, message=text)
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
        dismiss_after_id = self.after(timeout, lambda c=card: self.dismiss_toast(c))
        self._pending_dismiss_after_ids[card] = dismiss_after_id

    def show_toast(
        self,
        message: str,
        *,
        level: str = "info",
        duration_ms: int | None = None,
    ) -> None:
        self.notify(message, level=level, duration_ms=duration_ms)

    def dismiss_toast(self, card: tk.Frame) -> None:
        after_id = self._pending_dismiss_after_ids.pop(card, None)
        if after_id is not None:
            try:
                self.after_cancel(after_id)
            except tk.TclError:
                pass
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

    def history(self, *, limit: int | None = None) -> tuple[NotificationEntry, ...]:
        if limit is None:
            return tuple(self._history)
        max_items = max(0, int(limit))
        if max_items == 0:
            return ()
        return tuple(self._history[-max_items:])

    def clear_history(self) -> None:
        self._history.clear()
        self._refresh_history_tree()

    def show_history_dialog(self, *, title: str = "Notification History") -> None:
        if self._history_dialog is not None and self._history_dialog.winfo_exists():
            self._history_dialog.lift()
            self._history_dialog.focus_force()
            return

        top = tk.Toplevel(self)
        self._history_dialog = top
        top.title(title)
        top.transient(self.winfo_toplevel())
        top.geometry("760x360")
        top.minsize(520, 260)
        top.bind("<Destroy>", self._on_history_dialog_destroy, add="+")

        body = ttk.Frame(top, padding=12)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        tree = ttk.Treeview(body, columns=("time", "level", "message"), show="headings", height=12)
        tree.heading("time", text="Time")
        tree.heading("level", text="Level")
        tree.heading("message", text="Message")
        tree.column("time", width=160, anchor="w")
        tree.column("level", width=80, anchor="w")
        tree.column("message", width=480, anchor="w")
        tree.grid(row=0, column=0, sticky="nsew")

        y_scroll = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=y_scroll.set)
        y_scroll.grid(row=0, column=1, sticky="ns")

        actions = ttk.Frame(body)
        actions.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="Clear history", command=self.clear_history).pack(side="left")
        ttk.Button(actions, text="Close", command=top.destroy).pack(side="right")

        self._history_tree = tree
        self._refresh_history_tree()

    def _append_history(self, *, level: str, message: str) -> None:
        entry = NotificationEntry(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            level=level,
            message=message,
        )
        self._history.append(entry)
        overflow = len(self._history) - self.max_history
        if overflow > 0:
            del self._history[:overflow]
        self._refresh_history_tree()

    def _refresh_history_tree(self) -> None:
        tree = self._history_tree
        if tree is None or not tree.winfo_exists():
            return
        for child in tree.get_children():
            tree.delete(child)
        for entry in reversed(self._history):
            tree.insert("", tk.END, values=(entry.timestamp, entry.level.upper(), entry.message))

    def _on_history_dialog_destroy(self, event) -> None:
        if self._history_dialog is not None and event.widget is self._history_dialog:
            self._history_dialog = None
            self._history_tree = None

    def _on_destroy(self, event) -> None:
        if event.widget is not self:
            return
        for after_id in list(self._pending_dismiss_after_ids.values()):
            try:
                self.after_cancel(after_id)
            except tk.TclError:
                pass
        self._pending_dismiss_after_ids.clear()
        if self._history_dialog is not None and self._history_dialog.winfo_exists():
            try:
                self._history_dialog.destroy()
            except tk.TclError:
                pass


class ToastCenter(NotificationCenter):
    """Backward-compatible alias for NotificationCenter."""
