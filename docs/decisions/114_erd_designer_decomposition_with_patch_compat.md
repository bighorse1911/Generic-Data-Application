# 114 - ERD Designer Decomposition With Patch Compatibility

## Context

- `src/erd_designer.py` remained the final hard-budget readability hotspot (>1200 LOC).
- ERD behavior is reused across classic/v2 tool surfaces and includes strict actionable error contracts.
- Existing tests rely on legacy patch targets such as `mock.patch("src.erd_designer._find_ghostscript_executable", ...)`.

## Decision

- Decompose ERD concerns into domain-first modules under `src/gui/erd/`:
  - `common.py`
  - `authoring.py`
  - `project_io.py`
  - `layout.py`
  - `svg.py`
  - `raster.py`
- Keep `src/erd_designer.py` as a thin compatibility facade that:
  - re-exports stable public symbols,
  - preserves module-level patch targets (`_find_ghostscript_executable`, `_export_raster_with_ghostscript`),
  - routes `export_erd_file` through facade wrappers so patched finder behavior remains effective.
- Add import/facade contract tests for ERD symbol parity and patch behavior.
- Remove `src/erd_designer.py` from module-size hard exemptions after reduction below hard cap.

## Consequences

- ERD authoring/layout/export ownership is navigable by concern, reducing cognitive load.
- Legacy imports and patch points remain backward compatible for existing callers/tests.
- Hard module-size budget no longer requires a dedicated exemption for `src/erd_designer.py`.
- Remaining hotspot focus shifts to `src/gui/schema/editor/layout.py`.
