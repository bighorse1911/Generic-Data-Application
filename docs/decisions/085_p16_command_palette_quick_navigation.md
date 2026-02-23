# 085 - P16 Command Palette + Quick Navigation

## Context
- Priority P16 in `NEXT_DECISIONS.md` required faster cross-route navigation and high-frequency action access.
- Existing keyboard shortcuts were route-scoped only, so switching routes or triggering core actions required manual navigation.
- Productivity goals for P16 included one global launcher (`Ctrl/Cmd+K`) without breaking existing route-local shortcut behavior.

## Decision
- Add a reusable command-palette module in `src/gui_kit/command_palette.py`:
  - `CommandPaletteAction` model,
  - `CommandPaletteRegistry` for action registration/search/dispatch,
  - `CommandPalette` dialog UI with searchable results and keyboard activation.
- Integrate global command-palette launch in `App` (`src/gui_home.py`):
  - bind global `Ctrl/Cmd+K`,
  - expose route-jump actions for all v2 routes,
  - register active-route high-frequency actions for `schema_project_v2`, `run_center_v2`, `performance_workbench_v2`, and `execution_orchestrator_v2`.
- Keep existing route-scoped `ShortcutManager` behavior unchanged and additive.
- Export command-palette primitives through `src/gui_kit/__init__.py` and catalog metadata.

## Consequences
- Users can jump routes and trigger core workflows from one keyboard-first launcher.
- Route-level shortcuts continue to work because command palette is global-additive rather than replacing route bindings.
- Added regression coverage:
  - `tests/test_gui_kit_command_palette.py` for registry search/dispatch behavior,
  - `tests/test_gui_command_palette.py` for global launch, route/action coverage, and coexistence with route-scoped shortcuts.
