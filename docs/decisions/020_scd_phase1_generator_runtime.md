# Context
- Task requested implementing new SCD and Business Key logic in `generator_project.py`.
- Existing canon already defined SCD1/SCD2 semantics; runtime behavior was not fully implemented yet.

# Decision
- Implemented SCD phase 1 runtime behavior with backward-compatible schema evolution:
  - Added optional table-level config fields in `TableSpec` for `business_key`, `scd_mode`, `scd_tracked_columns`, `scd_active_from_column`, and `scd_active_to_column`.
  - Added actionable validation for business key and SCD configuration in `validate_project()`.
  - Added JSON IO support for SCD/business-key table fields in `load_project_from_json()`.
  - Added generator logic:
    - business-key uniqueness enforcement,
    - SCD1 overwrite-in-place behavior (single-row-per-business-key semantics),
    - SCD2 history-row expansion with deterministic non-overlapping active periods (`date`/`datetime`) and current-row marker.
  - Added targeted tests for SCD1/SCD2 generation, validation errors, and JSON roundtrip.
- Phase 1 scope constraint:
  - `scd2` is validated for root tables only (no incoming FKs) to avoid FK cardinality regressions in this slice.

# Consequences
- SCD1/SCD2 semantics now execute in runtime generation with deterministic output.
- Invalid SCD/business-key configs fail early with actionable fix hints.
- Existing JSON schemas remain backward compatible because new table fields are optional.
- GUI controls for authoring SCD fields remain pending for a follow-on phase.
