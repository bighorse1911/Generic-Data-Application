from __future__ import annotations

import json
from pathlib import Path

from src.gui_kit.run_commands import apply_run_center_payload
from src.gui_kit.run_commands import run_center_payload
from src.gui.v2.routes import run_hooks
from src.gui_v2.viewmodels import RunCenterViewModel
from src.schema_project_io import load_project_from_json


def _sync_viewmodel_from_vars(self) -> RunCenterViewModel:
    return self.surface.sync_model_from_vars()


def _browse_schema_path(self) -> None:
    path = run_hooks.filedialog.askopenfilename(
        title="Select schema project JSON",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
    )
    if path:
        self.surface.schema_path_var.set(path)


def _load_schema(self) -> bool:
    model = self._sync_viewmodel_from_vars()
    if model.schema_path == "":
        self.error_surface.emit(
            location="Schema path",
            issue="path is required",
            hint="choose an existing schema project JSON file",
            mode="mixed",
        )
        return False
    try:
        loaded = load_project_from_json(model.schema_path)
    except (ValueError, OSError) as exc:
        self.error_surface.emit_exception_actionable(
            exc,
            location="Load schema",
            hint="choose a valid schema project JSON file",
            mode="mixed",
        )
        return False
    self.project = loaded
    self._loaded_schema_path = model.schema_path
    self.shell.set_status(f"Loaded schema '{loaded.name}' with {len(loaded.tables)} tables.")
    self.surface.set_inline_error("")
    return True


def _ensure_project(self) -> bool:
    model = self._sync_viewmodel_from_vars()
    if self.project is None:
        return self._load_schema()
    if model.schema_path == "":
        return True
    if model.schema_path != self._loaded_schema_path:
        return self._load_schema()
    return True


def _save_profile(self) -> None:
    model = self._sync_viewmodel_from_vars()
    output_path = run_hooks.filedialog.asksaveasfilename(
        title="Save Run Center v2 config JSON",
        defaultextension=".json",
        initialfile=f"{model.profile_name}.json",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
    )
    if output_path == "":
        self.shell.set_status("Save config cancelled.")
        return

    payload = run_center_payload(model)
    try:
        Path(output_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        self.error_surface.emit(
            location="Save config",
            issue=f"could not write config file ({exc})",
            hint="choose a writable output path",
            mode="mixed",
        )
        return
    self._notify(f"Saved config to {output_path}.", level="success", duration_ms=3200)


def _load_profile(self) -> None:
    input_path = run_hooks.filedialog.askopenfilename(
        title="Load Run Center v2 config JSON",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
    )
    if input_path == "":
        self.shell.set_status("Load config cancelled.")
        return
    try:
        payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        self.error_surface.emit(
            location="Load config",
            issue=f"failed to read JSON ({exc})",
            hint="choose a valid JSON config file",
            mode="mixed",
        )
        return
    if not isinstance(payload, dict):
        self.error_surface.emit(
            location="Load config",
            issue="config JSON must be an object",
            hint="store config fields in a JSON object",
            mode="mixed",
        )
        return

    apply_run_center_payload(self.view_model, payload)
    self.surface.sync_vars_from_model()
    self._notify(f"Loaded config from {input_path}.", level="success", duration_ms=3200)

