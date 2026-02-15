from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

__all__ = ["JobLifecycleController", "JobLifecycleState"]


@dataclass
class JobLifecycleState:
    is_running: bool = False
    phase: str = "Idle"
    started_at: float = 0.0
    last_error: str = ""


class JobLifecycleController:
    """Shared async lifecycle helper for non-run background jobs."""

    def __init__(
        self,
        *,
        set_running: Callable[[bool, str], None],
        run_async: Callable[
            [Callable[[], object], Callable[[object], None], Callable[[Exception], None]],
            None,
        ],
        time_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self.state = JobLifecycleState()
        self._set_running_cb = set_running
        self._run_async_cb = run_async
        self._time_fn = time_fn

    def _set_running(self, running: bool, phase: str) -> None:
        self.state.is_running = bool(running)
        self.state.phase = str(phase)
        if running:
            self.state.started_at = float(self._time_fn())
            self.state.last_error = ""
        self._set_running_cb(running, phase)

    def run_async(
        self,
        *,
        worker: Callable[[], object],
        on_done: Callable[[object], None],
        on_failed: Callable[[str], None],
        phase_label: str,
        success_phase: str | None = None,
        failure_phase: str | None = None,
    ) -> bool:
        if self.state.is_running:
            return False
        self._set_running(True, phase_label)

        def _ok(payload: object) -> None:
            self.state.is_running = False
            if success_phase is not None:
                self._set_running(False, success_phase)
            on_done(payload)

        def _err(exc: Exception) -> None:
            message = str(exc)
            self.state.last_error = message
            self.state.is_running = False
            if failure_phase is not None:
                self._set_running(False, failure_phase)
            on_failed(message)

        self._run_async_cb(worker, _ok, _err)
        return True

