# Decision 102: GUI Domain Refactor (Compatibility-First)

## Context
GUI orchestration modules were large and top-level.

## Decision
Move canonical GUI implementations to:
- `src/gui/schema/classic_screen.py`
- `src/gui/schema/editor_base.py`
- `src/gui/v2/routes/_route_impl.py` + per-route export modules

Keep top-level files as shims:
- `src/gui_schema_core.py`
- `src/gui_schema_editor_base.py`
- `src/gui_v2_redesign.py`

## Consequences
- Existing route and import contracts are preserved.
- New GUI work has clearer package locations.
