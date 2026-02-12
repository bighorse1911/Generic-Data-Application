# Context
- Priority 1 error-contract alignment was completed, but several GUI validation paths still surfaced raw Python parse errors from `int()`/`float()` conversions.
- The affected flows were seed parsing, table row-count parsing, column min/max numeric parsing, and FK cardinality parsing in `src/gui_schema_project.py`.

# Decision
- Added canonical GUI validation wrapping for those parse errors using the existing `_gui_error()` contract:
  - `Project / Seed`,
  - `Table editor / Root row count`,
  - `Add column / Min value`,
  - `Add column / Max value`,
  - `Add relationship / Cardinality` (min/max integer parsing).
- Added GUI regression assertions in `tests/test_invariants.py` to enforce canonical `Location + issue + Fix` formatting for:
  - invalid seed,
  - invalid column min value.

# Consequences
- Invalid GUI numeric/text input now consistently returns actionable canonical validation messages instead of raw conversion trace text.
- Behavior remains backward-compatible for schema JSON, generation, FK integrity, and navigation; only validation wording/guardrails changed.
- Full suite remains green with these guardrails in place.
