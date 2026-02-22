from __future__ import annotations

from dataclasses import dataclass
import json
import tkinter as tk
from tkinter import filedialog
from tkinter import ttk

from src.config import AppConfig
from src.gui_kit.forms import FormBuilder
from src.gui_kit.json_editor import JsonEditorDialog
from src.gui_schema_editor_base import SchemaEditorBaseScreen
from src.gui_schema_shared import default_generator_params_template
from src.gui_v2.generator_forms import CROSS_CUTTING_FIELDS
from src.gui_v2.generator_forms import GeneratorFieldSpec
from src.gui_v2.generator_forms import format_field_value
from src.gui_v2.generator_forms import get_generator_form_spec
from src.gui_v2.generator_forms import parse_field_text
from src.gui_v2.generator_forms import split_form_state
from src.gui_v2.generator_forms import visible_fields_for

V2_HEADER_BG = "#0f2138"
V2_HEADER_FG = "#f5f5f5"
V2_ACTION_BG = "#d9d2c4"
V2_ACTION_FG = "#1f1f1f"


@dataclass
class _FieldBinding:
    spec: GeneratorFieldSpec
    var: tk.StringVar
    input_widget: tk.Widget
    action_button: ttk.Button | None = None


class SchemaProjectV2Screen(SchemaEditorBaseScreen):
    """Native v2 schema authoring route with canonical schema-editor behavior."""

    def __init__(self, parent: tk.Widget, app: object, cfg: AppConfig) -> None:
        self._generator_form_bindings: dict[str, _FieldBinding] = {}
        self._advanced_form_bindings: dict[str, _FieldBinding] = {}
        self._unknown_generator_params: dict[str, object] = {}
        self._suspend_generator_sync = False
        self._params_trace_name: str | None = None
        super().__init__(parent, app, cfg)
        self._attach_generator_form_sync()
        self._rebuild_generator_form_fields()
        self._sync_generator_form_from_params_json()

    def build_columns_panel(self):  # type: ignore[override]
        panel = super().build_columns_panel()
        editor_box = self._find_column_editor_box(panel)
        if editor_box is not None:
            self._install_generator_form_host(editor_box)
        return panel

    def build_header(self):  # type: ignore[override]
        header = tk.Frame(self._root_content, bg=V2_HEADER_BG, height=58)
        header.pack(fill="x", pady=(0, 10))
        header.pack_propagate(False)

        tk.Button(
            header,
            text="Back",
            command=self._on_back_requested,
            bg=V2_ACTION_BG,
            fg=V2_ACTION_FG,
            relief="flat",
            padx=10,
            pady=5,
        ).pack(side="left", padx=(8, 8), pady=8)
        tk.Label(
            header,
            text="Schema Project v2",
            bg=V2_HEADER_BG,
            fg=V2_HEADER_FG,
            font=("Cambria", 16, "bold"),
        ).pack(side="left", pady=8)
        tk.Label(
            header,
            textvariable=self._dirty_indicator_var,
            bg=V2_HEADER_BG,
            fg=V2_HEADER_FG,
            font=("Calibri", 10, "bold"),
        ).pack(side="left", padx=(10, 0), pady=8)

        tk.Button(
            header,
            text="Shortcuts",
            command=self._show_shortcuts_help,
            bg=V2_ACTION_BG,
            fg=V2_ACTION_FG,
            relief="flat",
            padx=10,
            pady=5,
        ).pack(side="right", padx=(0, 8), pady=8)
        return header

    def _on_back_requested(self) -> None:
        if self.confirm_discard_or_save(action_name="returning to Schema Studio v2"):
            self.app.show_screen("schema_studio_v2")

    # ---------------- Generator Form (v2-only) ----------------
    def _attach_generator_form_sync(self) -> None:
        if self._params_trace_name is None:
            self._params_trace_name = self.col_params_var.trace_add(
                "write",
                self._on_params_json_var_changed,
            )

    def _find_column_editor_box(self, panel: object) -> ttk.LabelFrame | None:
        body = getattr(panel, "body", None)
        if body is None:
            return None
        for child in body.winfo_children():
            if not isinstance(child, ttk.LabelFrame):
                continue
            try:
                label = str(child.cget("text")).strip().lower()
            except Exception:
                continue
            if label == "column editor":
                return child
        return None

    def _install_generator_form_host(self, editor_box: ttk.LabelFrame) -> None:
        if hasattr(self, "generator_form_box"):
            return

        editor_box.columnconfigure(0, weight=1)
        self.generator_form_box = ttk.LabelFrame(
            editor_box,
            text="Generator Configuration (v2)",
            padding=8,
        )
        self.generator_form_box.grid(row=6, column=0, sticky="ew", pady=(8, 0))
        self.generator_form_box.columnconfigure(0, weight=1)

        self.generator_form_message_var = tk.StringVar(
            value=(
                "Select a generator to configure structured fields. "
                "Raw Generator params JSON remains available below for edge cases."
            )
        )
        ttk.Label(
            self.generator_form_box,
            textvariable=self.generator_form_message_var,
            wraplength=620,
            justify="left",
        ).grid(row=0, column=0, sticky="ew")

        self.generator_fields_frame = ttk.Frame(self.generator_form_box)
        self.generator_fields_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.generator_fields_frame.columnconfigure(0, weight=1)

        self.generator_advanced_frame = ttk.LabelFrame(
            self.generator_form_box,
            text="Advanced Optional Params",
            padding=8,
        )
        self.generator_advanced_frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.generator_advanced_frame.columnconfigure(0, weight=1)

        actions = ttk.Frame(self.generator_form_box)
        actions.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)

        self.generator_reset_btn = ttk.Button(
            actions,
            text="Reset Structured Fields To Template",
            command=self._reset_generator_form_to_template,
        )
        self.generator_reset_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.generator_reload_btn = ttk.Button(
            actions,
            text="Reload Structured Fields From Raw JSON",
            command=self._reload_generator_form_from_json,
        )
        self.generator_reload_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))

    def _set_generator_form_message(self, message: str) -> None:
        if hasattr(self, "generator_form_message_var"):
            self.generator_form_message_var.set(message)

    def _current_table_column_names(self) -> list[str]:
        if self.selected_table_index is None:
            return []
        table = self.project.tables[self.selected_table_index]
        current_name = self.col_name_var.get().strip()
        return [name for name in (column.name for column in table.columns) if name != current_name]

    def _visible_generator_specs(self) -> list[GeneratorFieldSpec]:
        generator = self.col_generator_var.get().strip()
        dtype = self.col_dtype_var.get().strip().lower()
        return visible_fields_for(generator, dtype=dtype, include_cross_cutting=False)

    def _visible_advanced_specs(self) -> list[GeneratorFieldSpec]:
        dtype = self.col_dtype_var.get().strip().lower()
        return [spec for spec in CROSS_CUTTING_FIELDS if spec.is_visible_for_dtype(dtype)]

    def _clear_dynamic_form_rows(self) -> None:
        if hasattr(self, "generator_fields_frame"):
            for child in self.generator_fields_frame.winfo_children():
                child.destroy()
        if hasattr(self, "generator_advanced_frame"):
            for child in self.generator_advanced_frame.winfo_children():
                child.destroy()
        self._generator_form_bindings.clear()
        self._advanced_form_bindings.clear()

    def _rebuild_generator_form_fields(self) -> None:
        if not hasattr(self, "generator_fields_frame"):
            return

        self._clear_dynamic_form_rows()

        generator = self.col_generator_var.get().strip()
        if generator == "":
            self._set_generator_form_message(
                "No generator selected. Raw Generator params JSON remains fully supported."
            )
            self._set_generator_form_enabled(self.selected_table_index is not None and not self.is_running)
            return

        spec = get_generator_form_spec(generator)
        if spec is None:
            self._set_generator_form_message(
                f"No structured spec registered for generator '{generator}'. "
                "Use Raw Generator params JSON for this configuration."
            )
            self._set_generator_form_enabled(self.selected_table_index is not None and not self.is_running)
            return

        column_choices = self._current_table_column_names()
        form = FormBuilder(self.generator_fields_frame)
        for field_spec in self._visible_generator_specs():
            binding = self._build_field_binding(
                form,
                self.generator_fields_frame,
                field_spec,
                column_choices=column_choices,
            )
            self._generator_form_bindings[field_spec.field_id] = binding

        advanced_specs = self._visible_advanced_specs()
        if advanced_specs:
            self.generator_advanced_frame.grid()
            advanced_form = FormBuilder(self.generator_advanced_frame)
            for field_spec in advanced_specs:
                binding = self._build_field_binding(
                    advanced_form,
                    self.generator_advanced_frame,
                    field_spec,
                    column_choices=column_choices,
                )
                self._advanced_form_bindings[field_spec.field_id] = binding
        else:
            self.generator_advanced_frame.grid_remove()

        descriptor = spec.description.strip()
        if descriptor:
            self._set_generator_form_message(
                f"Structured fields for '{generator}': {descriptor}. "
                "Raw Generator params JSON can still include extra keys."
            )
        else:
            self._set_generator_form_message(
                f"Structured fields for '{generator}'. Raw Generator params JSON remains available."
            )
        self._set_generator_form_enabled(self.selected_table_index is not None and not self.is_running)

    def _build_field_binding(
        self,
        form: FormBuilder,
        parent: tk.Widget,
        field_spec: GeneratorFieldSpec,
        *,
        column_choices: list[str],
    ) -> _FieldBinding:
        var = tk.StringVar(value="")
        var.trace_add("write", self._on_generator_form_field_changed)

        action_button: ttk.Button | None = None

        if field_spec.control_kind == "combo":
            widget = ttk.Combobox(
                parent,
                textvariable=var,
                values=list(field_spec.options),
                state="readonly",
            )
            form.add_widget(field_spec.label, widget)
            return _FieldBinding(field_spec, var, widget, action_button)

        if field_spec.control_kind == "column":
            values = [""] + column_choices
            widget = ttk.Combobox(
                parent,
                textvariable=var,
                values=values,
                state="readonly",
            )
            form.add_widget(field_spec.label, widget)
            return _FieldBinding(field_spec, var, widget, action_button)

        if field_spec.control_kind == "path":
            holder = ttk.Frame(parent)
            holder.columnconfigure(0, weight=1)
            entry = ttk.Entry(holder, textvariable=var)
            entry.grid(row=0, column=0, sticky="ew")
            action_button = ttk.Button(
                holder,
                text="Browse...",
                command=lambda v=var: self._browse_generator_path(v),
            )
            action_button.grid(row=0, column=1, sticky="e", padx=(6, 0))
            form.add_widget(field_spec.label, holder)
            return _FieldBinding(field_spec, var, entry, action_button)

        if field_spec.control_kind == "json_object":
            holder = ttk.Frame(parent)
            holder.columnconfigure(0, weight=1)
            entry = ttk.Entry(holder, textvariable=var)
            entry.grid(row=0, column=0, sticky="ew")
            action_button = ttk.Button(
                holder,
                text="Edit JSON...",
                command=lambda s=field_spec, v=var: self._open_structured_object_editor(s, v),
            )
            action_button.grid(row=0, column=1, sticky="e", padx=(6, 0))
            form.add_widget(field_spec.label, holder)
            return _FieldBinding(field_spec, var, entry, action_button)

        widget = ttk.Entry(parent, textvariable=var)
        form.add_widget(field_spec.label, widget)
        return _FieldBinding(field_spec, var, widget, action_button)

    def _browse_generator_path(self, target_var: tk.StringVar) -> None:
        path = filedialog.askopenfilename(
            title="Select CSV file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if path:
            target_var.set(path)

    def _open_structured_object_editor(
        self,
        field_spec: GeneratorFieldSpec,
        target_var: tk.StringVar,
    ) -> None:
        JsonEditorDialog(
            self,
            title=f"{field_spec.label} JSON Editor",
            initial_text=target_var.get() or "{}",
            require_object=True,
            on_apply=lambda pretty_json: target_var.set(pretty_json),
        )

    def _on_generator_form_field_changed(self, *_args) -> None:
        if self._suspend_generator_sync:
            return
        self._sync_params_json_from_generator_form(
            require_required_fields=False,
            raise_on_error=False,
        )

    def _on_params_json_var_changed(self, *_args) -> None:
        if self._suspend_generator_sync:
            return
        self._sync_generator_form_from_params_json()

    def _parse_params_json_object(self) -> tuple[dict[str, object] | None, str | None]:
        raw = self.col_params_var.get().strip()
        if raw == "":
            return {}, None
        try:
            parsed = json.loads(raw)
        except Exception as exc:
            return None, (
                "Generator params JSON currently contains invalid JSON. "
                f"Fix: correct the JSON syntax. Details: {exc}"
            )
        if not isinstance(parsed, dict):
            return None, "Generator params JSON must be an object. Fix: use a JSON object payload."
        return parsed, None

    def _sync_generator_form_from_params_json(self) -> None:
        if not hasattr(self, "generator_fields_frame"):
            return

        generator = self.col_generator_var.get().strip()
        dtype = self.col_dtype_var.get().strip().lower()
        params, parse_error = self._parse_params_json_object()
        if parse_error is not None:
            self._set_generator_form_message(parse_error)
            return
        assert params is not None

        state = split_form_state(generator, dtype=dtype, params=params)
        self._unknown_generator_params = dict(state.passthrough_params)

        self._suspend_generator_sync = True
        try:
            for field_id, binding in self._generator_form_bindings.items():
                binding.var.set(format_field_value(binding.spec, state.known_params.get(field_id)))
            for field_id, binding in self._advanced_form_bindings.items():
                binding.var.set(format_field_value(binding.spec, state.known_params.get(field_id)))
        finally:
            self._suspend_generator_sync = False

        if self._unknown_generator_params:
            unknown_keys = ", ".join(sorted(self._unknown_generator_params.keys()))
            self._set_generator_form_message(
                "Structured fields synced from Raw Generator params JSON. "
                f"Preserving unknown passthrough keys: {unknown_keys}."
            )

    def _collect_structured_params(
        self,
        *,
        require_required_fields: bool,
    ) -> tuple[dict[str, object], list[str]]:
        values: dict[str, object] = {}
        errors: list[str] = []

        def _consume(binding: _FieldBinding) -> None:
            raw = binding.var.get()
            if raw.strip() == "":
                if require_required_fields and binding.spec.required:
                    errors.append(
                        f"Column editor / Generator config / {binding.spec.label}: value is required. "
                        "Fix: provide a value or use Raw Generator params JSON."
                    )
                return
            try:
                parsed = parse_field_text(binding.spec, raw)
            except ValueError as exc:
                errors.append(
                    f"Column editor / Generator config / {binding.spec.label}: {exc}. "
                    "Fix: correct this field or use Raw Generator params JSON."
                )
                return
            if parsed is None:
                return
            values[binding.spec.field_id] = parsed

        for binding in self._generator_form_bindings.values():
            _consume(binding)
        for binding in self._advanced_form_bindings.values():
            _consume(binding)

        generator = self.col_generator_var.get().strip()
        dtype = self.col_dtype_var.get().strip().lower()
        if generator == "choice_weighted":
            choices = values.get("choices")
            weights = values.get("weights")
            if isinstance(choices, list) and isinstance(weights, list) and len(weights) > 0:
                if len(choices) != len(weights):
                    errors.append(
                        "Column editor / Generator config / Weights (comma): weight count must match choices count. "
                        "Fix: provide one weight per choice."
                    )
        if generator == "sample_csv":
            match_column = values.get("match_column")
            has_match_column = isinstance(match_column, str) and match_column.strip() != ""
            has_match_index = "match_column_index" in values
            if has_match_column and require_required_fields and not has_match_index:
                errors.append(
                    "Column editor / Generator config / Match column index: value is required when Match source column is set. "
                    "Fix: set Match column index or clear Match source column."
                )
            if (not has_match_column) and ("match_column_index" in values):
                errors.append(
                    "Column editor / Generator config / Match column index: requires Match source column. "
                    "Fix: set Match source column or clear Match column index."
                )
        if generator == "time_offset":
            if dtype == "date":
                values.pop("min_seconds", None)
                values.pop("max_seconds", None)
            if dtype == "datetime":
                values.pop("min_days", None)
                values.pop("max_days", None)
        if dtype != "bytes":
            values.pop("min_length", None)
            values.pop("max_length", None)

        return values, errors

    def _dependency_source_values(self, params: dict[str, object]) -> list[str]:
        names: list[str] = []
        for binding in self._generator_form_bindings.values():
            if not binding.spec.dependency_source:
                continue
            value = params.get(binding.spec.field_id)
            if isinstance(value, str):
                stripped = value.strip()
                if stripped != "":
                    names.append(stripped)
        return names

    def _ensure_depends_on_contains(self, source_column: str) -> None:
        source = source_column.strip()
        if source == "":
            return
        current_column_name = self.col_name_var.get().strip()
        if source == current_column_name:
            return
        existing = [part.strip() for part in self.col_depends_var.get().split(",") if part.strip()]
        if source in existing:
            return
        existing.append(source)
        self.col_depends_var.set(", ".join(existing))

    def _sync_params_json_from_generator_form(
        self,
        *,
        require_required_fields: bool,
        raise_on_error: bool,
    ) -> bool:
        if self._suspend_generator_sync:
            return True
        generator = self.col_generator_var.get().strip()
        if generator == "":
            return True

        values, errors = self._collect_structured_params(require_required_fields=require_required_fields)
        if errors:
            if raise_on_error:
                raise ValueError("\n".join(errors))
            self._set_generator_form_message(errors[0])
            return False

        merged: dict[str, object] = dict(self._unknown_generator_params)
        merged.update(values)

        dtype = self.col_dtype_var.get().strip().lower()
        if generator == "time_offset":
            if dtype == "date":
                merged.pop("min_seconds", None)
                merged.pop("max_seconds", None)
            if dtype == "datetime":
                merged.pop("min_days", None)
                merged.pop("max_days", None)
        if generator == "sample_csv":
            match_column = merged.get("match_column")
            if not (isinstance(match_column, str) and match_column.strip()):
                merged.pop("match_column_index", None)

        payload = json.dumps(merged, sort_keys=True) if merged else ""

        self._suspend_generator_sync = True
        try:
            self.col_params_var.set(payload)
        finally:
            self._suspend_generator_sync = False

        for source_name in self._dependency_source_values(values):
            self._ensure_depends_on_contains(source_name)
        return True

    def _reload_generator_form_from_json(self) -> None:
        self._sync_generator_form_from_params_json()
        self.set_status("Reloaded structured generator fields from Raw Generator params JSON.")

    def _reset_generator_form_to_template(self) -> None:
        generator = self.col_generator_var.get().strip()
        dtype = self.col_dtype_var.get().strip()
        if generator == "":
            self._show_error_dialog(
                "Generator template",
                "Column editor / Generator config: no generator selected. "
                "Fix: choose a generator before resetting to template.",
            )
            return
        template = default_generator_params_template(generator, dtype)
        if template is None:
            self._show_error_dialog(
                "Generator template",
                f"Column editor / Generator config: no template is defined for generator '{generator}'. "
                "Fix: enter params manually in structured fields or Raw Generator params JSON.",
            )
            return

        self._unknown_generator_params = {}
        self._suspend_generator_sync = True
        try:
            for field_id, binding in self._generator_form_bindings.items():
                binding.var.set(format_field_value(binding.spec, template.get(field_id)))
            for field_id, binding in self._advanced_form_bindings.items():
                binding.var.set(format_field_value(binding.spec, template.get(field_id)))
        finally:
            self._suspend_generator_sync = False

        self._sync_params_json_from_generator_form(
            require_required_fields=False,
            raise_on_error=False,
        )
        self._set_generator_form_message(
            f"Reset structured fields to template for generator '{generator}'."
        )
        self._show_toast(f"Reset structured fields for '{generator}'.", level="success")

    def _set_generator_form_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        combo_state = "readonly" if enabled else tk.DISABLED

        for binding in self._generator_form_bindings.values():
            if isinstance(binding.input_widget, ttk.Combobox):
                binding.input_widget.configure(state=combo_state)
            else:
                binding.input_widget.configure(state=state)
            if binding.action_button is not None:
                binding.action_button.configure(state=state)

        for binding in self._advanced_form_bindings.values():
            if isinstance(binding.input_widget, ttk.Combobox):
                binding.input_widget.configure(state=combo_state)
            else:
                binding.input_widget.configure(state=state)
            if binding.action_button is not None:
                binding.action_button.configure(state=state)

        if hasattr(self, "generator_reset_btn"):
            self.generator_reset_btn.configure(state=state)
        if hasattr(self, "generator_reload_btn"):
            self.generator_reload_btn.configure(state=state)

    # ---------------- Overrides ----------------
    def _on_column_generator_changed(self, *_args) -> None:
        super()._on_column_generator_changed(*_args)
        self._rebuild_generator_form_fields()
        self._sync_generator_form_from_params_json()

    def _on_column_dtype_changed(self, *_args) -> None:
        super()._on_column_dtype_changed(*_args)
        self._rebuild_generator_form_fields()
        self._sync_generator_form_from_params_json()

    def _on_column_selected(self, _event=None) -> None:
        super()._on_column_selected(_event)
        self._rebuild_generator_form_fields()
        self._sync_generator_form_from_params_json()

    def _clear_column_editor(self) -> None:
        super()._clear_column_editor()
        self._rebuild_generator_form_fields()
        self._sync_generator_form_from_params_json()

    def _apply_generator_params_template(self) -> None:
        super()._apply_generator_params_template()
        self._sync_generator_form_from_params_json()

    def _on_params_json_apply(self, pretty_json: str) -> None:
        super()._on_params_json_apply(pretty_json)
        self._sync_generator_form_from_params_json()

    def _set_table_editor_enabled(self, enabled: bool) -> None:
        super()._set_table_editor_enabled(enabled)
        self._set_generator_form_enabled(enabled and (not self.is_running))

    def _add_column(self) -> None:
        try:
            self._sync_params_json_from_generator_form(
                require_required_fields=True,
                raise_on_error=True,
            )
        except Exception as exc:
            self._show_error_dialog("Add column failed", str(exc))
            return
        super()._add_column()

    def _apply_selected_column_changes(self) -> None:
        try:
            self._sync_params_json_from_generator_form(
                require_required_fields=True,
                raise_on_error=True,
            )
        except Exception as exc:
            self._show_error_dialog("Edit column failed", str(exc))
            return
        super()._apply_selected_column_changes()
