from __future__ import annotations


def _on_back_requested(self) -> None:
    if self.confirm_discard_or_save(action_name="returning to Schema Studio v2"):
        self.app.show_screen("schema_studio_v2")


def _on_main_tab_changed(self, _event=None) -> None:
    try:
        selected = self.main_tabs.select()
        if selected and str(selected) == str(self.generate_tab):
            self._refresh_preview()
    except Exception:
        pass
    self._persist_workspace_state()
    self._refresh_onboarding_hints()


def _on_screen_destroy(self, event) -> None:
    if event is None or getattr(event, "widget", None) is not self:
        return
    self._cancel_validation_debounce()
    if hasattr(self, "shortcut_manager"):
        self.shortcut_manager.deactivate()
    trace_name = getattr(self, "_schema_design_mode_trace_name", None)
    if trace_name is not None:
        try:
            self.schema_design_mode_var.trace_remove("write", trace_name)
        except Exception:
            pass
        self._schema_design_mode_trace_name = None
    self._persist_workspace_state()


