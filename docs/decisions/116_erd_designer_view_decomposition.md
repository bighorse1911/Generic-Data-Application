# 116 - ERD Designer View Concern Decomposition

## Context

- `src/gui_tools/erd_designer_view.py` (1019 LOC) was the next GUI readability/navigation hotspot.
- The frame is used directly by v2 specialist routes and has method-level behavior exercised by GUI tests.
- Refactor constraints required strict no-behavior-change parity with stable import and widget/state contracts.

## Decision

- Decompose ERD tool-frame concerns into `src/gui_tools/erd_designer/`:
  - `build.py`
  - `helpers.py`
  - `authoring_sync.py`
  - `authoring_actions.py`
  - `io_export.py`
  - `rendering.py`
  - `dragging.py`
- Keep `src/gui_tools/erd_designer_view.py` as a thin compatibility facade that:
  - defines `ERDDesignerToolFrame`,
  - preserves all existing method names as wrappers,
  - binds module context via setdefault so extracted concern modules retain the same global symbol access and patchability model used in prior GUI slices.
- Extend contract coverage:
  - add `tests/gui/test_erd_designer_view_method_contracts.py`,
  - extend `tests/test_import_contracts.py` for `src.gui_tools.erd_designer_view` and `src.gui_tools`,
  - extend static ErrorSurface gate coverage to all `src/gui_tools/erd_designer/*.py` modules.

## Consequences

- `erd_designer_view.py` is now a thin compatibility layer (213 LOC), removing it as a size hotspot.
- ERD tool-frame behavior is easier to navigate and modify by concern while preserving route/test compatibility.
- Existing `src.erd_designer` patch contracts remain unchanged and out of scope for this slice.
