# 092 - DG04 Safe Derived-Expression Engine

## Context
- `NEXT_DECISIONS.md` prioritized DG04 to provide realistic same-row derived-column logic without introducing unsafe dynamic execution.
- Existing generator set supported conditional and temporal transformations, but lacked a general constrained formula mechanism.
- DG04 required additive rollout across validator/runtime/GUI/docs/tests with strict deterministic behavior and actionable error surfaces.

## Decision
- Added new safe expression module `src/derived_expression.py`:
  - AST-validated DSL compiler with explicit allowlist and complexity guards.
  - Reference extraction for identifier refs and `col("...")`.
  - Deterministic evaluator with strict null/type/cast/runtime failures.
  - Supported DSL surface: arithmetic/comparison/boolean operators, conditional expressions, and approved helper functions (`if_else`, `coalesce`, `abs`, `round`, `min`, `max`, `concat`, `is_null`, `to_int`, `to_decimal`, `to_text`, `to_bool`, `col`).
- Added schema validation contract in `src/schema_project_model.py` for `generator="derived_expr"`:
  - requires non-empty `params.expression`,
  - blocks `bytes` target dtype,
  - rejects self-reference/unknown references,
  - requires every referenced source column to appear in `depends_on`.
- Added runtime generator in `src/generators.py`:
  - registered `derived_expr`,
  - compile/cache per table+column and clear cache via runtime-state reset,
  - strict target-dtype compatibility checks (`int`, `decimal|float`, `text`, `bool`, `date`, `datetime`) with actionable errors.
- Extended generator runtime context in `src/generator_project.py` to pass target dtype into `GenContext`.
- Added GUI authoring integration:
  - classic schema editor (`src/gui_schema_core.py`) now lists `derived_expr`, provides a default params template, validates expression syntax, and auto-appends inferred source references to `depends_on`.
  - v2 generator forms (`src/gui_v2/generator_forms.py`) include structured required `expression` field for `derived_expr`.
  - v2 schema editor (`src/gui_v2_schema_project.py`) validates expression edits and auto-infers dependency additions from expression references while preserving unknown params passthrough.
- Added guide/docs updates:
  - generation guide entry in `src/gui_tools/generation_guide_view.py`,
  - canonical updates in `DATA_SEMANTICS.md`, `PROJECT_CANON.md`, `GUI_WIREFRAME_SCHEMA.md`, `NEXT_DECISIONS.md`.

## Consequences
- Schemas can now express deterministic same-row derived formulas through `derived_expr` without using `eval`.
- Safety and predictability improve through strict AST constraints, explicit dependency declaration, and fail-fast runtime behavior.
- GUI authoring friction is reduced via template support and dependency auto-assist for expression references.
- DG04 is now marked completed; roadmap focus moves to DG05+ while retaining regression coverage for expression safety and determinism.
