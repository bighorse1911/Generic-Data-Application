# 115 - Editor Layout Concern Decomposition

## Context

- `src/gui/schema/editor/layout.py` was still a large readability hotspot (~1k LOC) after the `editor_base.py` concern split.
- `SchemaEditorBaseScreen` method wrappers and route-level patchability must remain stable.
- Schema v2 behavior contracts are test-sensitive (`_header_host`, schema-design modes, onboarding hints, shortcut/focus lifecycle, workspace-state restore).

## Decision

- Decompose layout concerns into same-folder modules under `src/gui/schema/editor/`:
  - `layout_build.py`
  - `layout_modes.py`
  - `layout_panels.py`
  - `layout_navigation.py`
  - `layout_shortcuts.py`
  - `layout_onboarding.py`
- Keep `src/gui/schema/editor/layout.py` as a thin compatibility hub that re-exports the legacy method names.
- Preserve `SchemaEditorBaseScreen` wrapper names/call patterns in `src/gui/schema/editor_base.py` and keep module-context binding for patch compatibility.
- Add/maintain method-contract coverage in `tests/gui/test_editor_layout_method_contracts.py` and validate parity with targeted GUI tests plus `run_gui_tests_isolated.py`.

## Consequences

- `layout.py` is now a small compatibility surface (<250 LOC) and no longer a hotspot.
- Layout behavior ownership is easier to navigate by concern without breaking import or wrapper contracts.
- GUI regressions remain green under isolated module execution, reducing risk before the next hotspot decomposition slice.
