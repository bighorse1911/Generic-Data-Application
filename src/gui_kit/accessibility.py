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
        return safe_focus(anchor.resolver())

    def focus_default(self) -> bool:
        if self._default_anchor_id is None:
            return False
        return self.focus(self._default_anchor_id)

    def focus_next(self, *, delta: int = 1) -> bool:
        if not self._order:
            return False
        if self._default_anchor_id and self._default_anchor_id in self._order:
            current_idx = self._order.index(self._default_anchor_id)
        else:
            current_idx = 0
        target_idx = (current_idx + int(delta)) % len(self._order)
        self._default_anchor_id = self._order[target_idx]
        return self.focus_default()

    def anchor_ids(self) -> tuple[str, ...]:
        return tuple(self._order)
