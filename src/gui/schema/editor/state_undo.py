from __future__ import annotations

def _mark_dirty_if_project_changed(self, before_project, *, reason: str) -> None:
    if self.project != before_project:
        self.mark_dirty(reason)


def _workspace_store(self) -> WorkspacePreferencesStore | None:
    store = getattr(self.app, "workspace_preferences", None)
    if isinstance(store, WorkspacePreferencesStore):
        return store
    return None


def _workspace_panel_state(self) -> dict[str, bool]:
    state: dict[str, bool] = {}
    for panel_key in ("project", "tables", "columns", "relationships", "generate"):
        panel = getattr(self, f"{panel_key}_panel", None)
        if isinstance(panel, CollapsiblePanel):
            state[panel_key] = bool(panel.is_collapsed)
    return state


def _workspace_preview_column_state(self) -> dict[str, list[str]]:
    payload: dict[str, list[str]] = {}
    for table_name, columns in self._preview_column_preferences.items():
        if not isinstance(table_name, str):
            continue
        clean_table = table_name.strip()
        if clean_table == "":
            continue
        if not isinstance(columns, list):
            continue
        clean_columns = [str(col).strip() for col in columns if str(col).strip() != ""]
        if not clean_columns:
            continue
        payload[clean_table] = clean_columns
    return payload


def _workspace_state_payload(self) -> dict[str, object]:
    tab_index = 0
    try:
        selected_tab = self.main_tabs.select()
        if selected_tab:
            tab_index = int(self.main_tabs.index(selected_tab))
    except Exception:
        tab_index = 0
    page_size = self.preview_page_size_var.get().strip()
    return {
        "version": 1,
        "main_tab_index": tab_index,
        "panel_state": self._workspace_panel_state(),
        "preview_page_size": page_size,
        "preview_column_preferences": self._workspace_preview_column_state(),
        "schema_design_mode": self._current_schema_design_mode(),
    }


def _persist_workspace_state(self) -> None:
    store = self._workspace_store()
    if store is None:
        return
    try:
        payload = self._workspace_state_payload()
    except Exception:
        return
    try:
        store.save_route_state(self.WORKSPACE_STATE_ROUTE_KEY, payload)
    except Exception:
        # Workspace-state persistence is best-effort and must not break route behavior.
        return


def _restore_workspace_state(self) -> None:
    store = self._workspace_store()
    if store is None:
        return
    try:
        payload = store.get_route_state(self.WORKSPACE_STATE_ROUTE_KEY)
    except Exception:
        return
    if not isinstance(payload, dict):
        return

    restored_mode = normalize_schema_design_mode(payload.get("schema_design_mode"))
    self._schema_design_mode_suspended = True
    try:
        self.schema_design_mode_var.set(restored_mode)
    finally:
        self._schema_design_mode_suspended = False

    raw_columns = payload.get("preview_column_preferences")
    if isinstance(raw_columns, dict):
        restored_columns: dict[str, list[str]] = {}
        for table_name, columns in raw_columns.items():
            if not isinstance(table_name, str) or not isinstance(columns, list):
                continue
            clean_table = table_name.strip()
            if clean_table == "":
                continue
            clean_columns = [str(col).strip() for col in columns if str(col).strip() != ""]
            if clean_columns:
                restored_columns[clean_table] = clean_columns
        self._preview_column_preferences = restored_columns

    page_size_raw = payload.get("preview_page_size")
    page_size_text = str(page_size_raw).strip() if page_size_raw is not None else ""
    if page_size_text != "":
        try:
            page_size_value = int(page_size_text)
            if page_size_value > 0:
                self.preview_page_size_var.set(str(page_size_value))
                self.preview_table.set_page_size(page_size_value)
        except Exception:
            pass

    panel_state = payload.get("panel_state")
    if isinstance(panel_state, dict):
        for panel_key, collapsed in panel_state.items():
            if not isinstance(panel_key, str):
                continue
            panel = getattr(self, f"{panel_key}_panel", None)
            if not isinstance(panel, CollapsiblePanel):
                continue
            should_collapse = bool(collapsed)
            if should_collapse:
                panel.collapse()
            else:
                panel.expand()

    tab_index_raw = payload.get("main_tab_index")
    try:
        tab_index = int(tab_index_raw)
    except Exception:
        tab_index = 0
    tab_count = len(self.main_tabs.tabs())
    if tab_count <= 0:
        return
    normalized = min(max(0, tab_index), tab_count - 1)
    self.main_tabs.select(normalized)


def _capture_undo_snapshot(self) -> EditorUndoSnapshot:
    selected_column_index: int | None = None
    selected_fk_index: int | None = None
    try:
        selected_column_index = self._selected_column_index()
    except Exception:
        selected_column_index = None
    try:
        selected_fk_index = self._selected_fk_index()
    except Exception:
        selected_fk_index = None
    return EditorUndoSnapshot(
        project=self.project,
        selected_table_index=self.selected_table_index,
        selected_column_index=selected_column_index,
        selected_fk_index=selected_fk_index,
    )


def _apply_undo_snapshot(self, snapshot: EditorUndoSnapshot) -> None:
    self._cancel_validation_debounce()
    self._suspend_project_meta_dirty = True
    try:
        self.project = snapshot.project
        self.project_name_var.set(self.project.name)
        self.seed_var.set(str(self.project.seed))
        self.project_timeline_constraints_var.set(
            json.dumps(self.project.timeline_constraints, sort_keys=True) if self.project.timeline_constraints else ""
        )
        self.project_data_quality_profiles_var.set(
            json.dumps(self.project.data_quality_profiles, sort_keys=True)
            if self.project.data_quality_profiles
            else ""
        )
        self.project_sample_profile_fits_var.set(
            json.dumps(self.project.sample_profile_fits, sort_keys=True)
            if self.project.sample_profile_fits
            else ""
        )
        self.project_locale_identity_bundles_var.set(
            json.dumps(self.project.locale_identity_bundles, sort_keys=True)
            if self.project.locale_identity_bundles
            else ""
        )
    finally:
        self._suspend_project_meta_dirty = False

    self.selected_table_index = None
    self._refresh_tables_list()
    self._refresh_fk_dropdowns()
    self._refresh_fks_tree()

    target_table_index = snapshot.selected_table_index
    if target_table_index is not None and 0 <= target_table_index < len(self.project.tables):
        self.selected_table_index = target_table_index
        self.tables_list.selection_clear(0, tk.END)
        self.tables_list.selection_set(target_table_index)
        self.tables_list.activate(target_table_index)
        self.tables_list.see(target_table_index)
        self._load_selected_table_into_editor()
    else:
        self._set_table_editor_enabled(False)
        self._clear_column_editor()
        self._refresh_columns_tree()

    if snapshot.selected_column_index is not None:
        self._show_column_source_index(snapshot.selected_column_index)
        if self.columns_tree.selection():
            self._on_column_selected()

    if snapshot.selected_fk_index is not None:
        self._show_fk_source_index(snapshot.selected_fk_index)

    self._stage_full_validation()
    self._run_validation_full()


def _record_undo_snapshot(
    self,
    *,
    before: EditorUndoSnapshot,
    label: str,
    reason: str,
) -> None:
    after = self._capture_undo_snapshot()
    if after.project == before.project:
        self._update_undo_redo_controls()
        return
    command = SnapshotCommand[EditorUndoSnapshot](
        label=label,
        apply_state=self._apply_undo_snapshot,
        before_state=before,
        after_state=after,
    )
    self.undo_stack.push(command)
    self._sync_dirty_from_saved_baseline(default_reason=reason)
    self._update_undo_redo_controls()


def _sync_dirty_from_saved_baseline(self, *, default_reason: str) -> None:
    if self.project == self._undo_saved_project:
        self.mark_clean()
        return
    self.mark_dirty(default_reason)


def _mark_saved_baseline(self) -> None:
    self._undo_saved_project = self.project
    self.mark_clean()
    self._update_undo_redo_controls()


def _reset_undo_history(self) -> None:
    self.undo_stack.clear()
    self._undo_saved_project = self.project
    self.mark_clean()
    self._update_undo_redo_controls()


def _undo_blocker_reason(self) -> str | None:
    if self.is_running:
        return (
            "Cannot modify undo/redo history while generation/export is running. "
            "Fix: wait for the active run to finish or cancel it."
        )
    if self._project_io_busy():
        return (
            "Cannot modify undo/redo history while project save/load is running. "
            "Fix: wait for project save/load to finish."
        )
    return None


def _update_undo_redo_controls(self) -> None:
    undo_btn = getattr(self, "undo_btn", None)
    redo_btn = getattr(self, "redo_btn", None)
    if undo_btn is None or redo_btn is None:
        return

    blocker = self._undo_blocker_reason()
    can_undo = blocker is None and self.undo_stack.can_undo
    can_redo = blocker is None and self.undo_stack.can_redo
    undo_btn.configure(state=(tk.NORMAL if can_undo else tk.DISABLED))
    redo_btn.configure(state=(tk.NORMAL if can_redo else tk.DISABLED))

    undo_label = self.undo_stack.undo_label
    redo_label = self.undo_stack.redo_label
    undo_text = "Undo" if not undo_label else f"Undo: {undo_label}"
    redo_text = "Redo" if not redo_label else f"Redo: {redo_label}"
    undo_btn.configure(text=undo_text)
    redo_btn.configure(text=redo_text)


def _undo_last_change(self) -> None:
    blocker = self._undo_blocker_reason()
    if blocker is not None:
        self.set_status(blocker)
        return
    try:
        command = self.undo_stack.undo()
    except Exception as exc:
        self._show_error_dialog(
            "Undo failed",
            f"Undo action: failed to apply previous schema state ({exc}). "
            "Fix: retry undo or continue editing and save/load project state.",
        )
        self._update_undo_redo_controls()
        return
    if command is None:
        self.set_status("Undo: no changes available.")
        self._update_undo_redo_controls()
        return
    self._sync_dirty_from_saved_baseline(default_reason="undo/redo changes")
    self._update_undo_redo_controls()
    self.set_status(f"Undo complete: {command.label}.")


def _redo_last_change(self) -> None:
    blocker = self._undo_blocker_reason()
    if blocker is not None:
        self.set_status(blocker)
        return
    try:
        command = self.undo_stack.redo()
    except Exception as exc:
        self._show_error_dialog(
            "Redo failed",
            f"Redo action: failed to re-apply schema state ({exc}). "
            "Fix: retry redo or continue editing and save/load project state.",
        )
        self._update_undo_redo_controls()
        return
    if command is None:
        self.set_status("Redo: no changes available.")
        self._update_undo_redo_controls()
        return
    self._sync_dirty_from_saved_baseline(default_reason="undo/redo changes")
    self._update_undo_redo_controls()
    self.set_status(f"Redo complete: {command.label}.")


def _on_project_meta_changed(self, *_args) -> None:
    if getattr(self, "_suspend_project_meta_dirty", False):
        return
    self.mark_dirty("project settings")
