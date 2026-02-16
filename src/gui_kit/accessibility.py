"""Keyboard focus helpers for screen-level accessibility flows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import tkinter as tk

__all__ = ["FocusAnchor", "FocusController", "safe_focus"]


@dataclass(frozen=True)
class FocusAnchor:
    anchor_id: str
    resolver: Callable[[], tk.Widget | None]
    description: str = ""


def safe_focus(widget: tk.Widget | None) -> bool:
    if widget is None:
        return False
    try:
        if not bool(widget.winfo_exists()):
            return False
        widget.focus_set()
        return True
    except tk.TclError:
        return False


class FocusController:
    """Screen focus anchor registry with default focus behavior."""

    def __init__(self, host: tk.Widget) -> None:
        self.host = host
        self._anchors: dict[str, FocusAnchor] = {}
        self._order: list[str] = []
        self._default_anchor_id: str | None = None
        self._last_focused_anchor_id: str | None = None

    def add_anchor(
        self,
        anchor_id: str,
        resolver: Callable[[], tk.Widget | None],
        *,
        description: str = "",
    ) -> None:
        key = str(anchor_id).strip()
        if key == "":
            raise ValueError(
                "Focus controller: anchor_id is required. "
                "Fix: provide a non-empty focus anchor id."
            )
        self._anchors[key] = FocusAnchor(key, resolver, description=description)
        if key not in self._order:
            self._order.append(key)

    def set_default_anchor(self, anchor_id: str) -> None:
        key = str(anchor_id).strip()
        if key not in self._anchors:
            raise KeyError(
                f"Focus controller: anchor '{key}' is not registered. "
                "Fix: register anchor before setting it as default."
            )
        self._default_anchor_id = key

    def focus(self, anchor_id: str) -> bool:
        key = str(anchor_id).strip()
        anchor = self._anchors.get(key)
        if anchor is None:
            return False
        widget = self._resolve_focusable_widget(anchor)
        if widget is None:
            return False
        focused = safe_focus(widget)
        if focused:
            self._last_focused_anchor_id = key
        return focused

    def focus_default(self) -> bool:
        if self._default_anchor_id is None:
            return False
        return self.focus(self._default_anchor_id)

    def focus_next(self, *, delta: int = 1) -> bool:
        if not self._order:
            return False
        step = -1 if int(delta) < 0 else 1
        start_anchor = self._last_focused_anchor_id
        if start_anchor is None:
            start_anchor = self._default_anchor_id
        if start_anchor in self._order:
            current_idx = self._order.index(start_anchor)
        else:
            current_idx = -1 if step > 0 else 0

        for offset in range(1, len(self._order) + 1):
            target_idx = (current_idx + (offset * step)) % len(self._order)
            target_id = self._order[target_idx]
            if self.focus(target_id):
                return True
        return False

    def focus_previous(self) -> bool:
        return self.focus_next(delta=-1)

    def anchor_ids(self) -> tuple[str, ...]:
        return tuple(self._order)

    @staticmethod
    def _resolve_focusable_widget(anchor: FocusAnchor) -> tk.Widget | None:
        widget = anchor.resolver()
        if widget is None:
            return None
        try:
            if not bool(widget.winfo_exists()):
                return None
            if not bool(widget.winfo_viewable()):
                return None
        except tk.TclError:
            return None
        return widget
