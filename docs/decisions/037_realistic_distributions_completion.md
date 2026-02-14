# Context
- Prompt requested completion of the in-progress item "Realistic distributions" with full validator/runtime/GUI coverage and no regressions.
- Existing runtime generators (`uniform_int`, `uniform_float`, `normal`, `lognormal`, `choice_weighted`) were partially exposed and lacked complete guardrails.

# Decision
- Completed the realistic distributions slice by:
  - adding canonical validator checks for distribution dtype compatibility and params shape/value constraints,
  - hardening runtime generator errors and clamping behavior (`normal` supports `stdev|stddev`; `lognormal` now supports optional `min|max` clamping),
  - exposing distribution and weighted generators in GUI column authoring (`GENERATORS` list + guide text),
  - adding focused unit tests for validator/runtime/GUI contracts.

# Consequences
- Distribution configs now fail fast with actionable location + fix-hint errors.
- GUI users can author realistic distribution generators directly without JSON-only workarounds.
- In-progress roadmap item "Realistic distributions" is now complete and documented in canon files.
