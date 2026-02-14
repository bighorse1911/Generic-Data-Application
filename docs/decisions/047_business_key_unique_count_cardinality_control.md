# Context
- Prompt requested table-generation behavior that supports:
  - configurable number of unique business keys, and
  - separate configurable total rows per table.
- Example use case: 200 unique employees across 2000 generated records.
- Constraints required deterministic generation, backward-compatible JSON, Tkinter GUI exposure, actionable validation errors, and no regressions.

# Decision
- Added optional table field `business_key_unique_count` to schema model/JSON/GUI.
- Updated validator/runtime guardrails:
  - requires `business_key` when `business_key_unique_count` is set,
  - requires positive integer,
  - requires `business_key_unique_count <= row_count` when row count is explicit,
  - for `scd1`, requires `business_key_unique_count == row_count`.
- Updated generation behavior:
  - default path unchanged when `business_key_unique_count` is unset,
  - when set, business-key assignment now targets exactly that unique-cardinality count,
  - added pre-sized SCD2 handling so final output row count remains aligned to table `row_count` while preserving non-overlapping periods and tracked-column mutation.
- Added table-editor control in both `schema_project_legacy` and `schema_project`/kit paths.

# Consequences
- Users can now model scenarios like many event/history rows per business key without manual post-processing.
- Existing JSON projects remain loadable without modification (new field is optional).
- Validation now surfaces clearer configuration errors before generation.
- Regression coverage expanded for:
  - validator guardrails,
  - generation cardinality behavior (including SCD2),
  - GUI authoring of `business_key_unique_count`.
