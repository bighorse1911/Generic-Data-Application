from collections.abc import Callable
from queue import Empty, Queue
from threading import Thread
import tkinter as tk
from tkinter import ttk


class BaseScreen(ttk.Frame):
    """
    Base pattern for modular app screens.
    """

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.status_var = tk.StringVar(value="Ready.")
        self._busy_widgets: list[ttk.Progressbar] = []

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
            ttk.Button(frame, text="← Back", command=back_command).pack(side="left")
        ttk.Label(frame, text=title, font=("Segoe UI", 16, "bold")).pack(side="left", padx=(10, 0))
        return frame

    def build_status_bar(self, parent: ttk.Frame, *, include_progress: bool = True) -> ttk.Frame:
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=(10, 0))

        ttk.Label(frame, textvariable=self.status_var).pack(side="left", anchor="w")
        if include_progress:
            progress = ttk.Progressbar(frame, mode="indeterminate", length=160)
            progress.pack(side="right")
            self.register_busy_indicator(progress)
        return frame

    def register_busy_indicator(self, progress: ttk.Progressbar) -> None:
        self._busy_widgets.append(progress)

    def set_status(self, text: str) -> None:
        self.status_var.set(text)

    def set_busy(self, busy: bool) -> None:
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
        queue: Queue[tuple[str, object]] = Queue(maxsize=1)
        Thread(target=self._run_job, args=(queue, fn), daemon=True).start()
        self.after(25, self._poll_job_queue, queue, on_ok, on_err)

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
    ) -> None:
        try:
            state, payload = queue.get_nowait()
        except Empty:
            self.after(25, self._poll_job_queue, queue, on_ok, on_err)
            return

        if state == "ok":
            on_ok(payload)
            return

        if on_err is not None:
            on_err(payload)  # type: ignore[arg-type]
