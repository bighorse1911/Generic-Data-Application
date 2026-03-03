# 111 - Classic Screen Concern Decomposition

## Context

- `src/gui/schema/classic_screen.py` was a major readability hotspot (>3600 LOC).
- Classic schema behavior is a high-sensitivity compatibility surface for both classic and v2 schema routes.
- The refactor required no behavior change while preserving legacy imports and patch points.

## Decision

- Decompose classic schema implementation into concern modules under `src/gui/schema/classic/`:
  - `constants.py`
  - `widgets.py`
  - `layout.py`
  - `state_dirty.py`
  - `validation.py`
  - `preview.py`
  - `project_io.py`
  - `actions_tables.py`
  - `actions_columns.py`
  - `actions_fks.py`
  - `actions_generation.py`
- Keep `src/gui/schema/classic_screen.py` as a thin compatibility hub:
  - preserve `SchemaProjectDesignerScreen` method names as wrappers,
  - preserve re-exports for constants/widgets,
  - preserve legacy module-level patch symbols (`filedialog`, `messagebox`, `save_project_to_json`, `load_project_from_json`).
- Keep `src/gui_schema_core.py` compatibility shim behavior unchanged.

## Consequences

- Classic schema ownership is now split by concern for easier navigation and safer incremental changes.
- `classic_screen.py` is reduced from a logic hotspot to a compatibility wrapper surface.
- Hard module-size exemption for `classic_screen.py` is removed while preserving behavior/test parity.
- Remaining decomposition focus shifts to runtime hotspots (`performance_scaling.py`, `multiprocessing_runtime.py`).
