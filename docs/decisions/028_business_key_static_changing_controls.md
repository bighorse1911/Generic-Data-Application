# Context
- User requested explicit business-key behavior controls so table authors can define which attributes remain static across records (for example last name) and which attributes change across records (for example address).
- The feature had to be implemented in both GUI authoring flows and generator/runtime logic, while preserving deterministic generation and JSON backward compatibility.

# Decision
- Added two optional table-level schema fields:
  - `business_key_static_columns`
  - `business_key_changing_columns`
- Implemented validator rules to enforce:
  - non-empty lists when provided,
  - known column names only,
  - no static/changing overlap,
  - business key columns cannot be in changing columns,
  - when both `business_key_changing_columns` and `scd_tracked_columns` are present, they must match.
- Updated SCD2 generator behavior to:
  - use `business_key_changing_columns` as the primary tracked-column source (fallback to `scd_tracked_columns`),
  - explicitly keep `business_key_static_columns` values stable across versions.
- Added GUI controls for both fields in legacy and modular schema project screens.
- Updated JSON load logic and unit tests for runtime, GUI, and validation coverage.

# Consequences
- Authors can now explicitly model stable versus changing business-key attributes in schema configuration.
- Existing schemas remain compatible because both new fields are optional and legacy `scd_tracked_columns` remains supported.
- Validation errors now catch invalid static/changing configurations with actionable fix hints before generation.
