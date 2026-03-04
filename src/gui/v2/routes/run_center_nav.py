from __future__ import annotations


def on_show(self) -> None:
    self.shortcut_manager.activate()
    self.focus_controller.focus_default()


def on_hide(self) -> None:
    self.shortcut_manager.deactivate()


def _register_focus_anchors(self) -> None:
    self.focus_controller.add_anchor(
        "schema_path",
        lambda: getattr(self.surface, "schema_entry", None),
        description="Schema path input",
    )
    self.focus_controller.add_anchor(
        "actions",
        lambda: self.start_run_btn,
        description="Run action controls",
    )
    self.focus_controller.add_anchor(
        "diagnostics",
        lambda: self.diagnostics_tree,
        description="Diagnostics table",
    )
    self.focus_controller.add_anchor(
        "plan",
        lambda: self.preview_table,
        description="Partition plan table",
    )
    self.focus_controller.add_anchor(
        "failures",
        lambda: self.failures_tree,
        description="Failures table",
    )
    self.focus_controller.add_anchor(
        "history",
        lambda: self.history_tree,
        description="Run history table",
    )
    self.focus_controller.set_default_anchor("schema_path")


def _register_shortcuts(self) -> None:
    self.shortcut_manager.register("<F1>", "Open shortcuts help", self._show_shortcuts_help)
    self.shortcut_manager.register("<F6>", "Focus next major section", self._focus_next_anchor)
    self.shortcut_manager.register("<Shift-F6>", "Focus previous major section", self._focus_previous_anchor)
    self.shortcut_manager.register_ctrl_cmd("b", "Browse schema path", self._browse_schema_path)
    self.shortcut_manager.register_ctrl_cmd("l", "Load schema", self._load_schema)
    self.shortcut_manager.register_ctrl_cmd("s", "Save run config", self._save_profile)
    self.shortcut_manager.register_ctrl_cmd("o", "Load run config", self._load_profile)
    self.shortcut_manager.register("<F5>", "Estimate workload", self._run_estimate)
    self.shortcut_manager.register_ctrl_cmd("Return", "Start run", self._start_generation)
    self.shortcut_manager.register("<Escape>", "Cancel active run", self._cancel_if_running)
    self.shortcut_manager.register_help_item("Ctrl/Cmd+C", "Copy selected table rows with headers")
    self.shortcut_manager.register_help_item("Ctrl/Cmd+Shift+C", "Copy selected table rows without headers")
    self.shortcut_manager.register_help_item("Ctrl/Cmd+A", "Select all rows in focused table")
    self.shortcut_manager.register_help_item("PageUp/PageDown", "Move selection by page in focused table")
    self.shortcut_manager.register_help_item("Ctrl/Cmd+Home", "Jump to first row in focused table")
    self.shortcut_manager.register_help_item("Ctrl/Cmd+End", "Jump to last row in focused table")


def _focus_next_anchor(self) -> None:
    self.focus_controller.focus_next()


def _focus_previous_anchor(self) -> None:
    self.focus_controller.focus_previous()


def _cancel_if_running(self) -> None:
    if self.lifecycle.state.is_running:
        self._cancel_run()


def _show_shortcuts_help(self) -> None:
    self.shortcut_manager.show_help_dialog(title="Run Center v2 Shortcuts")


def _show_notifications_history(self) -> None:
    if hasattr(self, "toast_center"):
        self.toast_center.show_history_dialog(title="Run Center Notifications")


def _notify(self, message: str, *, level: str = "info", duration_ms: int | None = None) -> None:
    text = str(message).strip()
    if text == "":
        return
    self.shell.set_status(text)
    if hasattr(self, "toast_center"):
        self.toast_center.notify(text, level=level, duration_ms=duration_ms)


def _set_inspector_for_config(self) -> None:
    self.shell.set_inspector(
        "Run Center Notes",
        [
            "Run Center v2 is wired to performance + multiprocessing runtimes.",
            "Estimate/plan/benchmark/start preserve canonical validation and deterministic semantics.",
            "Errors preserve location + fix hints.",
        ],
    )


def _set_focus(self, key: str) -> None:
    self.shell.set_nav_active(key)
    if key in {"diagnostics", "plan", "failures", "history"}:
        self.surface.set_focus(key)
    self.shell.set_status(f"Run Center v2: focus set to {key}.")

