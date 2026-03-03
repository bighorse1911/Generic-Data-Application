from __future__ import annotations



def _mark_dirty(self, reason: str | None = None) -> None:
    self._dirty = True
    text = "Unsaved changes"
    if reason:
        text = f"Unsaved: {reason}"
    self._dirty_indicator_var.set(f"[{text}]")

def _mark_clean(self) -> None:
    self._dirty = False
    self._dirty_indicator_var.set("")

def _on_project_meta_changed(self, *_args) -> None:
    if self._suspend_dirty_tracking:
        return
    self._mark_dirty("project settings")

def _mark_dirty_if_project_changed(self, before_project: SchemaProject, *, reason: str) -> None:
    if self.project != before_project:
        self._mark_dirty(reason)

def _confirm_discard_or_save(self, action_name: str) -> bool:
    if not self._dirty:
        return True
    action = action_name.strip() or "continuing"
    choice = messagebox.askyesnocancel(
        "Unsaved changes",
        "Schema Project Designer: unsaved changes detected before "
        f"{action}. Fix: choose Yes to save, No to discard, or Cancel to stay.",
    )
    if choice is None:
        return False
    if choice is False:
        return True
    saved = self._save_project()
    return bool(saved and not self._dirty)

def _show_error_dialog(self, location: str, message: object) -> str:
    return self.error_surface.emit_exception_actionable(
        message,
        location=(str(location).strip() or "Schema project"),
        hint="review the inputs and retry",
        mode="mixed",
    )

def _show_warning_dialog(self, location: str, message: object) -> str:
    warning_message = self.error_surface.emit_warning_actionable(
        message,
        location=(str(location).strip() or "Schema project"),
        hint="review the inputs and retry",
        mode="status",
    )
    self._notify(warning_message, level="warn", duration_ms=3200)
    return warning_message

def _notify(self, message: str, *, level: str = "info", duration_ms: int | None = None) -> None:
    text = str(message).strip()
    if text == "":
        return
    self.status_var.set(text)
    if hasattr(self, "toast_center"):
        self.toast_center.notify(text, level=level, duration_ms=duration_ms)

def _show_notifications_history(self) -> None:
    if hasattr(self, "toast_center"):
        self.toast_center.show_history_dialog(title="Schema Project Notifications")

def _ui_alive(self) -> bool:
    try:
        return bool(self.winfo_exists())
    except tk.TclError:
        return False

def _post_ui_callback(self, callback) -> None:
    safe_dispatch(self.after, callback, is_alive=self._ui_alive)

def _update_generate_enabled(self) -> None:
    """
    Enable Generate buttons only when there are no validation errors.
    Note: when is_running=True we still disable controls via _set_running().
    """
    if getattr(self, "is_running", False):
        return  # _set_running handles it

    ok = (self.last_validation_errors == 0)

    # Your main generate button
    if hasattr(self, "generate_btn"):
        self.generate_btn.configure(state=(tk.NORMAL if ok else tk.DISABLED))

    # Sample generate button (we'll add this in polish 4)
    if hasattr(self, "sample_btn"):
        self.sample_btn.configure(state=(tk.NORMAL if ok else tk.DISABLED))

