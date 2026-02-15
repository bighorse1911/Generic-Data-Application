from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

from src.gui_kit.ui_dispatch import UIDispatcher
from src.multiprocessing_runtime import MultiprocessEvent
from src.performance_scaling import RuntimeEvent

__all__ = [
    "RunLifecycleController",
    "RunLifecycleState",
    "RunProgressSnapshot",
    "multiprocess_event_to_snapshot",
    "runtime_event_to_snapshot",
]


@dataclass
class RunLifecycleState:
    is_running: bool = False
    cancel_requested: bool = False
    started_at: float = 0.0
    phase: str = "Idle"
    fallback_used: bool = False
    last_retry_count: int = 0
    last_event_kind: str = ""


@dataclass(frozen=True)
class RunProgressSnapshot:
    kind: str
    progress_value: float | None = None
    phase_text: str | None = None
    rows_text: str | None = None
    eta_text: str | None = None



def _eta_parts(rows_processed: int, total_rows: int, started_at: float, *, time_fn: Callable[[], float]) -> tuple[str, float]:
    elapsed = max(0.001, float(time_fn()) - float(started_at))
    rate = float(rows_processed) / elapsed if rows_processed > 0 else 0.0
    if rate <= 0.0:
        return "ETA: --", 0.0
    remaining = max(0, int(total_rows) - int(rows_processed))
    eta_seconds = int(round(float(remaining) / rate))
    return f"ETA: {eta_seconds}s @ {rate:.1f} rows/s", rate



def runtime_event_to_snapshot(
    event: RuntimeEvent,
    *,
    started_at: float,
    time_fn: Callable[[], float] = time.monotonic,
) -> RunProgressSnapshot:
    if event.kind == "started":
        return RunProgressSnapshot(
            kind=event.kind,
            progress_value=0.0,
            phase_text=event.message or "Run started.",
            rows_text=f"Rows processed: 0/{event.total_rows}",
            eta_text="ETA: calculating...",
        )

    if event.kind in {"progress", "table_done"}:
        total_rows = max(1, int(event.total_rows))
        processed = max(0, int(event.rows_processed))
        progress = min(100.0, (float(processed) / float(total_rows)) * 100.0)
        eta_text, _rate = _eta_parts(processed, total_rows, started_at, time_fn=time_fn)
        return RunProgressSnapshot(
            kind=event.kind,
            progress_value=progress,
            phase_text=event.message or "Running...",
            rows_text=f"Rows processed: {processed}/{event.total_rows}",
            eta_text=eta_text,
        )

    if event.kind == "run_done":
        elapsed = max(0.001, float(time_fn()) - float(started_at))
        rows_processed = max(0, int(event.rows_processed))
        rate = float(rows_processed) / elapsed if rows_processed > 0 else 0.0
        return RunProgressSnapshot(
            kind=event.kind,
            progress_value=100.0,
            phase_text=event.message or "Run complete.",
            rows_text=f"Rows processed: {event.rows_processed}/{event.total_rows}",
            eta_text=f"Completed in {elapsed:.2f}s @ {rate:.1f} rows/s",
        )

    if event.kind == "cancelled":
        return RunProgressSnapshot(
            kind=event.kind,
            phase_text=event.message or "Run cancelled.",
            eta_text="ETA: cancelled",
        )

    return RunProgressSnapshot(kind=event.kind)



def multiprocess_event_to_snapshot(
    event: MultiprocessEvent,
    *,
    started_at: float,
    time_fn: Callable[[], float] = time.monotonic,
) -> RunProgressSnapshot:
    if event.kind == "started":
        return RunProgressSnapshot(
            kind=event.kind,
            progress_value=0.0,
            phase_text=event.message or "Run started.",
            rows_text=f"Rows processed: 0/{event.total_rows}",
            eta_text="ETA: calculating...",
        )

    if event.kind == "progress":
        total_rows = max(1, int(event.total_rows))
        processed = max(0, int(event.rows_processed))
        progress = min(100.0, (float(processed) / float(total_rows)) * 100.0)
        eta_text, _rate = _eta_parts(processed, total_rows, started_at, time_fn=time_fn)
        return RunProgressSnapshot(
            kind=event.kind,
            progress_value=progress,
            phase_text=event.message or "Running...",
            rows_text=f"Rows processed: {processed}/{event.total_rows}",
            eta_text=eta_text,
        )

    if event.kind == "partition_failed":
        return RunProgressSnapshot(kind=event.kind, phase_text=event.message or "Partition failed.")

    if event.kind == "fallback":
        return RunProgressSnapshot(kind=event.kind, phase_text=event.message or "Fallback to single-process.", eta_text="ETA: fallback")

    if event.kind == "run_done":
        elapsed = max(0.001, float(time_fn()) - float(started_at))
        rows_processed = max(0, int(event.rows_processed))
        rate = float(rows_processed) / elapsed if rows_processed > 0 else 0.0
        return RunProgressSnapshot(
            kind=event.kind,
            progress_value=100.0,
            phase_text=event.message or "Run complete.",
            rows_text=f"Rows processed: {event.rows_processed}/{event.total_rows}",
            eta_text=f"Completed in {elapsed:.2f}s @ {rate:.1f} rows/s",
        )

    if event.kind == "cancelled":
        return RunProgressSnapshot(kind=event.kind, phase_text=event.message or "Run cancelled.", eta_text="ETA: cancelled")

    return RunProgressSnapshot(kind=event.kind)


class RunLifecycleController:
    """Shared start/cancel/progress/run-thread lifecycle helper."""

    def __init__(
        self,
        *,
        set_phase: Callable[[str], None],
        set_rows: Callable[[str], None],
        set_eta: Callable[[str], None],
        set_progress: Callable[[float], None],
        set_status: Callable[[str], None] | None,
        action_buttons: list[object],
        cancel_button: object,
        time_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self.state = RunLifecycleState()
        self._set_phase = set_phase
        self._set_rows = set_rows
        self._set_eta = set_eta
        self._set_progress = set_progress
        self._set_status = set_status
        self._action_buttons = action_buttons
        self._cancel_button = cancel_button
        self._time_fn = time_fn

    def _set_widget_state(self, widget: object, enabled: bool) -> None:
        if widget is None:
            return
        state_value = "normal" if enabled else "disabled"
        configure = getattr(widget, "configure", None)
        if callable(configure):
            configure(state=state_value)

    def set_running(self, running: bool, phase: str) -> None:
        self.state.is_running = bool(running)
        self.state.phase = str(phase)
        self._set_phase(self.state.phase)
        if running:
            self.state.started_at = float(self._time_fn())
            self.state.cancel_requested = False
            self.state.fallback_used = False
            self.state.last_retry_count = 0
            self.state.last_event_kind = ""
            self._set_progress(0.0)
            self._set_rows("Rows processed: 0")
            self._set_eta("ETA: --")
            self._set_widget_state(self._cancel_button, True)
            for button in self._action_buttons:
                self._set_widget_state(button, False)
            return
        self.state.cancel_requested = False
        self._set_widget_state(self._cancel_button, False)
        for button in self._action_buttons:
            self._set_widget_state(button, True)

    def request_cancel(self, status_text: str) -> None:
        if not self.state.is_running:
            return
        self.state.cancel_requested = True
        self._set_phase("Cancelling...")
        if self._set_status is not None:
            self._set_status(status_text)

    def is_cancel_requested(self) -> bool:
        return bool(self.state.cancel_requested)

    def apply_snapshot(self, snapshot: RunProgressSnapshot) -> RunProgressSnapshot:
        self.state.last_event_kind = snapshot.kind
        if snapshot.progress_value is not None:
            self._set_progress(float(snapshot.progress_value))
        if snapshot.phase_text is not None:
            self._set_phase(snapshot.phase_text)
        if snapshot.rows_text is not None:
            self._set_rows(snapshot.rows_text)
        if snapshot.eta_text is not None:
            self._set_eta(snapshot.eta_text)
        return snapshot

    def handle_runtime_event(self, event: RuntimeEvent) -> RunProgressSnapshot:
        snapshot = runtime_event_to_snapshot(event, started_at=self.state.started_at, time_fn=self._time_fn)
        return self.apply_snapshot(snapshot)

    def handle_multiprocess_event(self, event: MultiprocessEvent) -> RunProgressSnapshot:
        if event.kind == "fallback":
            self.state.fallback_used = True
        if int(event.retry_count) > self.state.last_retry_count:
            self.state.last_retry_count = int(event.retry_count)
        snapshot = multiprocess_event_to_snapshot(event, started_at=self.state.started_at, time_fn=self._time_fn)
        return self.apply_snapshot(snapshot)

    def transition_complete(self, phase: str) -> None:
        self.set_running(False, phase)

    def transition_failed(self, message: str, *, phase: str = "Failed") -> None:
        self.set_running(False, phase)
        if self._set_status is not None:
            self._set_status(message)

    def transition_cancelled(self, message: str, *, phase: str = "Cancelled") -> None:
        self.set_running(False, phase)
        if self._set_status is not None:
            self._set_status(message)

    def run_async(
        self,
        *,
        after: Callable[[int, Callable[[], None]], object],
        worker: Callable[[], object],
        on_done: Callable[[object], None],
        on_failed: Callable[[str], None],
        on_cancelled: Callable[[str], None],
        phase_label: str,
        cancel_exceptions: tuple[type[Exception], ...],
        dispatcher: UIDispatcher | None = None,
        is_ui_alive: Callable[[], bool] | None = None,
    ) -> bool:
        if self.state.is_running:
            return False

        self.set_running(True, phase_label)
        ui_dispatch = dispatcher or UIDispatcher(
            after=after,
            is_alive=(is_ui_alive or (lambda: True)),
        )

        def _dispatch_terminal(callback: Callable[[], None]) -> None:
            posted = ui_dispatch.post(callback)
            if not posted:
                self.state.is_running = False

        def work() -> None:
            try:
                result = worker()
            except cancel_exceptions as exc:
                _dispatch_terminal(lambda message=str(exc): on_cancelled(message))
                return
            except Exception as exc:  # noqa: BLE001
                _dispatch_terminal(lambda message=str(exc): on_failed(message))
                return
            _dispatch_terminal(lambda payload=result: on_done(payload))

        threading.Thread(target=work, daemon=True).start()
        return True
