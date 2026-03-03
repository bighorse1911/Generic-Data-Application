from __future__ import annotations

from src.gui_schema_core import SchemaProjectDesignerScreen

def _run_job_async(self, worker, on_done, on_failed) -> None:
    self.safe_threaded_job(worker, on_done, on_failed)


def _set_running(self, running: bool, msg: str) -> None:
    SchemaProjectDesignerScreen._set_running(self, running, msg)
    self._update_undo_redo_controls()
    self._refresh_onboarding_hints()


def _set_project_io_running(self, running: bool, msg: str) -> None:
    self._project_io_running = bool(running)
    self.set_status(msg)
    self.set_busy(running)
    save_btn = getattr(self, "save_project_btn", None)
    load_btn = getattr(self, "load_project_btn", None)
    validate_btn = getattr(self, "run_validation_btn", None)
    state = tk.DISABLED if running else tk.NORMAL
    for widget in (save_btn, load_btn, validate_btn):
        if widget is not None:
            widget.configure(state=state)
    self._update_undo_redo_controls()
    self._refresh_onboarding_hints()


def _project_io_busy(self) -> bool:
    return bool(self._project_io_running or self.project_io_lifecycle.state.is_running)


def _project_io_guard(self, *, action: str) -> bool:
    if self.is_running:
        self.set_status(
            f"Cannot {action}: a generation/export run is currently active. "
            "Fix: wait for the current run to finish or cancel it first."
        )
        return False
    if self._project_io_busy():
        self.set_status(
            f"Cannot {action}: a project save/load operation is already running. "
            "Fix: wait for the current project operation to finish."
        )
        return False
    return True


def _on_project_io_failed(self, title: str, message: str) -> None:
    self._show_error_dialog(title, str(message))
