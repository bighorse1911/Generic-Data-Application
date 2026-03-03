from __future__ import annotations

from dataclasses import dataclass
import json
import tkinter as tk
from tkinter import filedialog
from tkinter import ttk

from src import gui_v2_schema_project_form as v2_schema_form
from src import gui_v2_schema_project_layout as v2_schema_layout
from src.config import AppConfig
from src.derived_expression import extract_derived_expression_references
from src.gui_kit.forms import FormBuilder
from src.gui_kit.json_editor import JsonEditorDialog
from src.gui_kit.theme_tokens import V2_THEME
from src.gui_kit.theme_tokens import v2_button_options
from src.gui_schema_editor_base import SchemaEditorBaseScreen
from src.gui_schema_shared import default_generator_params_template
from src.gui_v2.generator_forms import CROSS_CUTTING_FIELDS
from src.gui_v2.generator_forms import GeneratorFieldSpec
from src.gui_v2.generator_forms import format_field_value
from src.gui_v2.generator_forms import get_generator_form_spec
from src.gui_v2.generator_forms import parse_field_text
from src.gui_v2.generator_forms import split_form_state
from src.gui_v2.generator_forms import visible_fields_for
from src.gui_v2.schema_design_modes import SchemaDesignMode

V2_HEADER_BG = V2_THEME.colors.header_bg
V2_HEADER_FG = V2_THEME.colors.header_fg


@dataclass
class _FieldBinding:
    spec: GeneratorFieldSpec
    var: tk.StringVar
    input_widget: tk.Widget
    action_button: ttk.Button | None = None


def _bind_v2_schema_module_context(module) -> None:
    for name, value in globals().items():
        if name.startswith("__"):
            continue
        module.__dict__.setdefault(name, value)


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
        return v2_schema_layout.build_columns_panel(self)

    def build_header(self):  # type: ignore[override]
        return v2_schema_layout.build_header(self)

    def _on_back_requested(self) -> None:
        return v2_schema_layout._on_back_requested(self)

    # ---------------- Generator Form (v2-only) ----------------
    def _attach_generator_form_sync(self) -> None:
        return v2_schema_form._attach_generator_form_sync(self)

    def _find_column_editor_box(self, panel: object) -> ttk.LabelFrame | None:
        return v2_schema_form._find_column_editor_box(self, panel)

    def _install_generator_form_host(self, editor_box: ttk.LabelFrame) -> None:
        return v2_schema_form._install_generator_form_host(self, editor_box)

    def _set_generator_form_message(self, message: str) -> None:
        return v2_schema_form._set_generator_form_message(self, message)

    def _current_table_column_names(self) -> list[str]:
        return v2_schema_form._current_table_column_names(self)

    def _visible_generator_specs(self) -> list[GeneratorFieldSpec]:
        return v2_schema_form._visible_generator_specs(self)

    def _visible_advanced_specs(self) -> list[GeneratorFieldSpec]:
        return v2_schema_form._visible_advanced_specs(self)

    def _clear_dynamic_form_rows(self) -> None:
        return v2_schema_form._clear_dynamic_form_rows(self)

    def _rebuild_generator_form_fields(self) -> None:
        return v2_schema_form._rebuild_generator_form_fields(self)

    def _build_field_binding(
        self,
        form: FormBuilder,
        parent: tk.Widget,
        field_spec: GeneratorFieldSpec,
        *,
        column_choices: list[str],
    ) -> _FieldBinding:
        return v2_schema_form._build_field_binding(
            self,
            form,
            parent,
            field_spec,
            column_choices=column_choices,
        )

    def _browse_generator_path(self, target_var: tk.StringVar) -> None:
        return v2_schema_form._browse_generator_path(self, target_var)

    def _open_structured_object_editor(
        self,
        field_spec: GeneratorFieldSpec,
        target_var: tk.StringVar,
    ) -> None:
        return v2_schema_form._open_structured_object_editor(self, field_spec, target_var)

    def _on_generator_form_field_changed(self, *_args) -> None:
        return v2_schema_form._on_generator_form_field_changed(self, *_args)

    def _on_params_json_var_changed(self, *_args) -> None:
        return v2_schema_form._on_params_json_var_changed(self, *_args)

    def _parse_params_json_object(self) -> tuple[dict[str, object] | None, str | None]:
        return v2_schema_form._parse_params_json_object(self)

    def _sync_generator_form_from_params_json(self) -> None:
        return v2_schema_form._sync_generator_form_from_params_json(self)

    def _collect_structured_params(
        self,
        *,
        require_required_fields: bool,
    ) -> tuple[dict[str, object], list[str]]:
        return v2_schema_form._collect_structured_params(
            self,
            require_required_fields=require_required_fields,
        )

    def _dependency_source_values(self, params: dict[str, object]) -> list[str]:
        return v2_schema_form._dependency_source_values(self, params)

    def _ensure_depends_on_contains(self, source_column: str) -> None:
        return v2_schema_form._ensure_depends_on_contains(self, source_column)

    def _sync_params_json_from_generator_form(
        self,
        *,
        require_required_fields: bool,
        raise_on_error: bool,
    ) -> bool:
        return v2_schema_form._sync_params_json_from_generator_form(
            self,
            require_required_fields=require_required_fields,
            raise_on_error=raise_on_error,
        )

    def _reload_generator_form_from_json(self) -> None:
        return v2_schema_form._reload_generator_form_from_json(self)

    def _reset_generator_form_to_template(self) -> None:
        return v2_schema_form._reset_generator_form_to_template(self)

    def _set_generator_form_enabled(self, enabled: bool) -> None:
        return v2_schema_form._set_generator_form_enabled(self, enabled)

    def _apply_generator_form_mode_visibility(self, mode: SchemaDesignMode | None = None) -> None:
        return v2_schema_form._apply_generator_form_mode_visibility(self, mode)

    def _apply_schema_design_mode_overrides(self, mode: SchemaDesignMode) -> None:
        return v2_schema_form._apply_schema_design_mode_overrides(self, mode)

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
        self._apply_generator_form_mode_visibility()

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


for _v2_schema_module in (
    v2_schema_layout,
    v2_schema_form,
):
    _bind_v2_schema_module_context(_v2_schema_module)


__all__ = [
    "SchemaProjectV2Screen",
    "_FieldBinding",
]

