# Context
- Prompt requested an option for `sample_csv` so one sampled column can depend on another sampled column from the same CSV row (for example `country=US` with `city=Seattle`).
- Existing `sample_csv` behavior sampled each column independently, which could break row-level combinations.
- Constraints required standard library only, deterministic generation, actionable validation errors, GUI accessibility where applicable, and no regressions.

# Decision
- Added optional dependent sampling mode to `sample_csv`:
  - `params.match_column`: source column name from the same generated row.
  - `params.match_column_index`: CSV column index used to match the source value.
- Runtime now filters candidate values by CSV row matches when `match_column` is configured.
- Validator now enforces source-column existence, non-self-reference, `depends_on` linkage, and integer/non-negative `match_column_index` rules.
- GUI guidance was updated in generation behavior help text to document dependent `sample_csv` usage.
- Canon documents (`PROJECT_CANON.md`, `NEXT_DECISIONS.md`, `DATA_SEMANTICS.md`, `GUI_WIREFRAME_SCHEMA.md`) were updated to record the behavior contract.

# Consequences
- Users can model correlated CSV fields (such as city-country pairs) without adding new dtypes or custom generators.
- Backward compatibility is preserved: existing `sample_csv` configs without dependency params continue working unchanged.
- New validation/runtime errors are explicit and actionable when dependency setup is incomplete or when CSV matches are unavailable.
- Added regression tests cover valid dependent sampling, deterministic behavior, validation guardrails, and runtime no-match errors.
