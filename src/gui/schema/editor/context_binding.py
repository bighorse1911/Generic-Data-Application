from __future__ import annotations


EDITOR_CONTEXT_MODULE_NAMES = (
    "editor_jobs",
    "editor_layout",
    "editor_layout_build",
    "editor_layout_modes",
    "editor_layout_panels",
    "editor_layout_panels_project",
    "editor_layout_panels_tables",
    "editor_layout_panels_columns",
    "editor_layout_panels_relationships",
    "editor_layout_panels_generate",
    "editor_layout_navigation",
    "editor_layout_shortcuts",
    "editor_layout_onboarding",
    "editor_validation",
    "editor_filters",
    "editor_preview",
    "editor_project_io",
    "editor_actions_tables",
    "editor_actions_columns",
    "editor_actions_fks",
    "editor_actions_generation",
    "editor_state_undo",
)


def _bind_editor_module_context(module: object, scope: dict[str, object]) -> None:
    for name, value in scope.items():
        if name.startswith("__"):
            continue
        module.__dict__.setdefault(name, value)


def bind_editor_modules_from_scope(scope: dict[str, object]) -> None:
    for module_name in EDITOR_CONTEXT_MODULE_NAMES:
        _bind_editor_module_context(scope[module_name], scope)


__all__ = [
    "EDITOR_CONTEXT_MODULE_NAMES",
    "bind_editor_modules_from_scope",
]
