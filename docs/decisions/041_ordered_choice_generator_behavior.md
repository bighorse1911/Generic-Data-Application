# Context
- Prompt requested a new generator behavior for ordered choices with multiple named orders and weighted movement through the sequence.
- Existing generators supported weighted categorical choice (`choice_weighted`) but did not support row-to-row ordered progression.

# Decision
- Added `ordered_choice` generator in runtime with:
  - required `params.orders` (named order paths),
  - optional `params.order_weights` (which path to pick),
  - optional `params.move_weights` (step-size movement weighting),
  - optional `params.start_index`.
- Added validator guardrails in `validate_project()` for `ordered_choice` params with canonical actionable error format.
- Exposed `ordered_choice` in GUI generator authoring:
  - included in generator dropdown,
  - included in dtype-based filtering (`text`, `int`),
  - included in params template defaults.
- Updated generation behavior guide and canonical docs to record the feature contract.

# Consequences
- Users can model deterministic staged progression paths (for example A: 1->2->3 or B: 4->5->6) with controllable movement weighting.
- Invalid `ordered_choice` configs fail fast with location + issue + fix hints before generation.
- Existing generation, FK integrity, GUI navigation, and JSON IO behaviors remain covered by passing tests.
