from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.gui_kit.error_contract import coerce_actionable_message
from src.gui_kit.error_contract import format_actionable_error
from src.gui_kit.error_contract import is_actionable_message

__all__ = [
    "actionable_error",
    "is_actionable_message",
    "show_error_dialog",
    "show_warning_dialog",
    "ErrorSurface",
]


def actionable_error(context: str, location: str, issue: str, hint: str) -> str:
    return format_actionable_error(context, location, issue, hint)


def show_error_dialog(title: str, message: str) -> None:
    from tkinter import messagebox

    messagebox.showerror(title, message)


def show_warning_dialog(title: str, message: str) -> None:
    from tkinter import messagebox

    messagebox.showwarning(title, message)


@dataclass
class ErrorSurface:
    """Unified adapter for dialog/status/inline error delivery."""

    context: str
    dialog_title: str
    warning_title: str | None = None
    show_dialog: Callable[[str, str], None] | None = None
    show_warning: Callable[[str, str], None] | None = None
    set_status: Callable[[str], None] | None = None
    set_inline: Callable[[str], None] | None = None

    def format(self, *, location: str, issue: str, hint: str) -> str:
        return actionable_error(self.context, location, issue, hint)

    def clear_inline(self) -> None:
        if self.set_inline is not None:
            self.set_inline("")

    def _emit_with_mode(
        self,
        message: str,
        *,
        mode: str,
        warning: bool,
    ) -> str:
        clean_mode = str(mode).strip().lower()
        if clean_mode not in {"dialog", "status", "inline", "mixed"}:
            clean_mode = "mixed"
        if clean_mode in {"mixed", "dialog"}:
            if warning and self.show_warning is not None:
                self.show_warning(self.warning_title or self.dialog_title, message)
            elif self.show_dialog is not None:
                self.show_dialog(self.dialog_title, message)
        if clean_mode in {"mixed", "status"} and self.set_status is not None:
            self.set_status(message)
        if clean_mode in {"mixed", "inline"} and self.set_inline is not None:
            self.set_inline(message)
        return message

    def emit_formatted(self, message: str, *, mode: str = "mixed") -> str:
        return self._emit_with_mode(message, mode=mode, warning=False)

    def emit_warning_formatted(self, message: str, *, mode: str = "mixed") -> str:
        return self._emit_with_mode(message, mode=mode, warning=True)

    def emit(
        self,
        *,
        location: str,
        issue: str,
        hint: str,
        mode: str = "mixed",
    ) -> str:
        message = self.format(location=location, issue=issue, hint=hint)
        return self.emit_formatted(message, mode=mode)

    def emit_warning(
        self,
        *,
        location: str,
        issue: str,
        hint: str,
        mode: str = "mixed",
    ) -> str:
        message = self.format(location=location, issue=issue, hint=hint)
        return self.emit_warning_formatted(message, mode=mode)

    def emit_exception(self, exc: Exception | str, *, mode: str = "mixed") -> str:
        message = str(exc)
        return self.emit_formatted(message, mode=mode)

    def emit_exception_actionable(
        self,
        exc: Exception | str,
        *,
        location: str,
        hint: str,
        mode: str = "mixed",
    ) -> str:
        message = coerce_actionable_message(
            self.context,
            exc,
            location=location,
            hint=hint,
        )
        return self.emit_formatted(message, mode=mode)

    def emit_warning_actionable(
        self,
        message: Exception | str,
        *,
        location: str,
        hint: str,
        mode: str = "mixed",
    ) -> str:
        normalized = coerce_actionable_message(
            self.context,
            message,
            location=location,
            hint=hint,
        )
        return self.emit_warning_formatted(normalized, mode=mode)
