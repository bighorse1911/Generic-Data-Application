# 119 - Schema V2 Route Concern Decomposition

## Context

- `src/gui_v2_schema_project.py` remained a soft-budget hotspot at 767 LOC.
- The route has high GUI-test coverage and participates in schema-authoring behavior relied on by v2 workflows.
- Refactor constraints required strict no-behavior-change parity with stable `SchemaProjectV2Screen` method surface and import path.

## Decision

- Decompose schema-v2 route concerns into sibling modules:
  - `src/gui_v2_schema_project_layout.py` for header/back/layout attachment helpers.
  - `src/gui_v2_schema_project_form.py` for structured generator-form build/sync/validation logic.
- Keep `src/gui_v2_schema_project.py` as the compatibility facade:
  - retain `SchemaProjectV2Screen` class and wrapper method names,
  - delegate extracted methods to concern modules,
  - preserve shared module-level symbol visibility by context-binding modules via `setdefault`.
- Add method-contract coverage:
  - `tests/gui/test_gui_v2_schema_project_method_contracts.py`,
  - extend `tests/test_import_contracts.py` to import new modules.

## Consequences

- `src/gui_v2_schema_project.py` is now a thin facade (247 LOC) and removed from soft module-size warnings.
- Generator-form behavior is easier to navigate and change safely by concern.
- Route behavior, user-visible error/status wording, and v2 GUI contracts remain parity-stable under existing tests.
