from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import tkinter as tk

__all__ = ["UIDispatcher", "safe_dispatch"]


def _widget_alive(widget: object) -> bool:
    winfo_exists = getattr(widget, "winfo_exists", None)
    if not callable(winfo_exists):
        return False
    try:
        return bool(winfo_exists())
    except tk.TclError:
        return False


def safe_dispatch(
    after: Callable[[int, Callable[[], None]], object],
    callback: Callable[[], None],
    *,
    delay_ms: int = 0,
    is_alive: Callable[[], bool] | None = None,
) -> bool:
    if is_alive is not None and not bool(is_alive()):
        return False
    try:
        after(max(0, int(delay_ms)), callback)
    except tk.TclError:
        return False
    return True


@dataclass(frozen=True)
class UIDispatcher:
    after: Callable[[int, Callable[[], None]], object]
    is_alive: Callable[[], bool]

    @classmethod
    def from_widget(cls, widget: object) -> "UIDispatcher":
        after_cb = getattr(widget, "after", None)
        if not callable(after_cb):
            raise ValueError(
                "UI dispatcher requires widget.after callback support. "
                "Fix: pass a Tk widget with an after() method."
            )
        return cls(after=after_cb, is_alive=lambda: _widget_alive(widget))

    def post(self, callback: Callable[[], None], *, delay_ms: int = 0) -> bool:
        return safe_dispatch(
            self.after,
            callback,
            delay_ms=delay_ms,
            is_alive=self.is_alive,
        )

    def marshal(self, callback: Callable[..., None]) -> Callable[..., None]:
        def _wrapped(*args, **kwargs) -> None:
            self.post(lambda: callback(*args, **kwargs))

        return _wrapped

