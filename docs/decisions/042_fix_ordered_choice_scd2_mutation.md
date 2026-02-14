# Context
- Prompt reported that using `ordered_choice` on a business-key changing column could produce invalid SCD2 second-version values (observed fallback to `0`).
- SCD2 tracked-column mutation was using generic dtype mutation logic, not ordered-choice progression semantics.

# Decision
- Updated SCD2 tracked-column mutation in `src/generator_project.py` to treat `generator='ordered_choice'` specially:
  - resolve the current value against configured order sequences,
  - apply configured `move_weights` progression for version steps,
  - clamp at sequence end.
- Hardened int tracked mutation fallback to avoid coercing non-int values to `0`.
- Added regression test coverage in `tests/test_scd_generation.py` to ensure ordered-choice progression is preserved across SCD2 versions.

# Consequences
- SCD2 version rows for ordered-choice changing columns now follow configured order progression instead of generic numeric mutation.
- The previously observed fallback-to-zero behavior is prevented in this path.
- Existing generation/validation/GUI/IO flows remain green under full test suite.
