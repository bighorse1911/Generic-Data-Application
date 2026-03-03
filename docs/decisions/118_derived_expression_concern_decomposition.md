# 118 - Derived Expression Concern Decomposition

## Context

- `src/derived_expression.py` was a soft-budget hotspot at 848 LOC.
- The module is used across schema validation, generation runtime, and GUI dependency assistance, so compatibility risk is non-trivial.
- This slice required strict no-behavior-change parity, including deterministic output and exact actionable error text.

## Decision

- Decompose `src/derived_expression.py` into top-level concern modules:
  - `src/derived_expression_common.py`
  - `src/derived_expression_types.py`
  - `src/derived_expression_validator.py`
  - `src/derived_expression_evaluator.py`
  - `src/derived_expression_compile.py`
  - `src/derived_expression_datetime.py`
- Keep `src/derived_expression.py` as the compatibility facade:
  - re-export stable public symbols (`CompiledDerivedExpression`, compile/evaluate/extract, ISO helpers, limits),
  - preserve private compatibility re-exports (`_ExpressionValidator`, `_ExpressionEvaluator`, `_expression_error`, `_is_scalar_literal`, `_is_number`).
- Add contract coverage:
  - `tests/generation/test_derived_expression_contracts.py`,
  - extended `tests/test_import_contracts.py` for explicit `src.derived_expression` symbol checks.

## Consequences

- `src/derived_expression.py` is now a thin facade and no longer appears in soft module-size warnings.
- Expression-engine ownership is clearer by concern (common/types/validator/evaluator/compile/datetime).
- Existing imports and behavior contracts remain stable for schema, generation, and GUI callers.
