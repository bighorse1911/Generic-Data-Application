"""Shared screen composition helpers for Tkinter views."""

from collections.abc import Callable
from queue import Empty, Queue
from threading import Thread
import tkinter as tk
from tkinter import messagebox, ttk

from src.gui_kit.ui_dispatch import UIDispatcher

__all__ = ["BaseScreen"]


class BaseScreen(ttk.Frame):
    """Base pattern for modular app screens."""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.status_var = tk.StringVar(value="Ready.")
        self._busy_widgets: list[ttk.Progressbar] = []
        self._dirty = False
        self._dirty_context = "Screen"
        self._dirty_save_callback: Callable[[], object] | None = None
        self._dirty_indicator_var = tk.StringVar(value="")

    def build(self) -> None:
        raise NotImplementedError("Screen subclasses should implement build().")

    def build_header(
        self,
        parent: ttk.Frame,
        *,
        title: str,
        back_command: Callable[[], None] | None = None,
    ) -> ttk.Frame:
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=(0, 10))

        if back_command is not None:
            ttk.Button(frame, text="<- Back", command=back_command).pack(side="left")
        ttk.Label(frame, text=title, font=("Segoe UI", 16, "bold")).pack(side="left", padx=(10, 0))
        ttk.Label(frame, textvariable=self._dirty_indicator_var).pack(side="left", padx=(8, 0))
        return frame

    def build_status_bar(self, parent: ttk.Frame, *, include_progress: bool = True) -> ttk.Frame:
        """Build a status line with optional indeterminate progress indicator."""

        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=(10, 0))

        ttk.Label(frame, textvariable=self.status_var).pack(side="left", anchor="w")
        if include_progress:
            progress = ttk.Progressbar(frame, mode="indeterminate", length=160)
            progress.pack(side="right")
            self.register_busy_indicator(progress)
        return frame

    def register_busy_indicator(self, progress: ttk.Progressbar) -> None:
        """Register a progress widget controlled by set_busy()."""

        self._busy_widgets.append(progress)

    def set_status(self, text: str) -> None:
        """Set user-visible status text."""

        self.status_var.set(text)

    def set_busy(self, busy: bool) -> None:
        """Start/stop all registered busy indicators."""

        for progress in self._busy_widgets:
            if busy:
                progress.start(10)
            else:
                progress.stop()

    def safe_threaded_job(
        self,
        fn: Callable[[], object],
        on_ok: Callable[[object], None],
        on_err: Callable[[Exception], None] | None = None,
    ) -> None:
        """Run work in a background thread and marshal result callbacks to Tk."""

        dispatcher = UIDispatcher.from_widget(self)
        queue: Queue[tuple[str, object]] = Queue(maxsize=1)
        Thread(target=self._run_job, args=(queue, fn), daemon=True).start()
        dispatcher.post(
            lambda: self._poll_job_queue(queue, on_ok, on_err, dispatcher=dispatcher),
            delay_ms=25,
        )

    @staticmethod
    def _run_job(queue: Queue[tuple[str, object]], fn: Callable[[], object]) -> None:
        try:
            queue.put(("ok", fn()))
        except Exception as exc:  # pragma: no cover - exercised through callbacks
            queue.put(("err", exc))

    def _poll_job_queue(
        self,
        queue: Queue[tuple[str, object]],
        on_ok: Callable[[object], None],
        on_err: Callable[[Exception], None] | None,
        dispatcher: UIDispatcher,
    ) -> None:
        try:
            state, payload = queue.get_nowait()
        except Empty:
            dispatcher.post(
                lambda: self._poll_job_queue(queue, on_ok, on_err, dispatcher=dispatcher),
                delay_ms=25,
            )
            return

        if state == "ok":
            on_ok(payload)
            return

        if on_err is not None:
            on_err(payload)  # type: ignore[arg-type]

    def enable_dirty_state_guard(
        self,
        *,
        context: str,
        on_save: Callable[[], object] | None = None,
    ) -> None:
        """Configure dirty-state behavior for unsaved-change prompts."""

        self._dirty_context = context.strip() or "Screen"
        self._dirty_save_callback = on_save

    @property
    def is_dirty(self) -> bool:
        """True when unsaved screen changes exist."""

        return self._dirty

    def mark_dirty(self, reason: str | None = None) -> None:
        """Mark this screen as having unsaved changes."""

        self._dirty = True
        text = "Unsaved changes"
        if reason:
            text = f"Unsaved: {reason}"
        self._dirty_indicator_var.set(f"[{text}]")

    def mark_clean(self) -> None:
        """Mark this screen as clean after save/load."""

        self._dirty = False
        self._dirty_indicator_var.set("")

    def confirm_discard_or_save(
        self,
        *,
        action_name: str,
        on_save: Callable[[], object] | None = None,
    ) -> bool:
        """
        Prompt when unsaved changes exist.

        Returns True when caller should continue with the requested action.
        """

        if not self._dirty:
            return True

        save_callback = on_save or self._dirty_save_callback
        action = action_name.strip() or "continue"
        context = self._dirty_context

        if save_callback is None:
            return bool(
                messagebox.askyesno(
                    "Unsaved changes",
                    f"{context}: unsaved changes detected before {action}. "
                    "Fix: choose Yes to continue and discard unsaved changes, or No to stay.",
                )
            )

        choice = messagebox.askyesnocancel(
            "Unsaved changes",
            f"{context}: unsaved changes detected before {action}. "
            "Fix: choose Yes to save, No to discard, or Cancel to stay.",
        )
        if choice is None:
            return False
        if choice is False:
            return True

        try:
            save_result = save_callback()
        except Exception as exc:  # pragma: no cover - UI callback path
            messagebox.showerror(
                "Save failed",
                f"{context}: save failed before {action} ({exc}). "
                "Fix: resolve the save error and retry.",
            )
            return False

        if save_result is False:
            return False
        if self._dirty:
            return False
        return True
