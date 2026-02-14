# Context
- Prompt requested reducing manual statement/regex entry in GUI authoring and ensuring generator options only show those valid for selected dtype.
- Existing column editor exposed a single global generator list and required fully manual params JSON/regex authoring.

# Decision
- Added dtype-aware generator filtering in column editor so generator options are constrained to valid dtype-compatible entries.
- Added regex pattern presets in column editor while keeping custom regex support.
- Added generator params template-fill action that seeds Params JSON for the selected generator/dtype.
- Added GUI validation guardrail: applying a column now fails fast when a generator/dtype mismatch is attempted.

# Consequences
- GUI authoring is safer and faster with less manual JSON/regex typing.
- Invalid generator/dtype combinations are blocked earlier with actionable fix hints.
- Existing JSON compatibility is preserved because custom params JSON and custom regex fields remain available.
