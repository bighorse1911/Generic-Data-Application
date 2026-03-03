# 124 - Generation Quality Profiles Concern Decomposition

## Context

- `src/generation/quality_profiles.py` remained a large mixed-concern module (~640 LOC).
- DG06 behavior is on the generation critical path and is consumed through compatibility imports from pipeline/orchestrator modules.
- This slice required strict no-behavior-change parity for deterministic output and actionable runtime error contracts.

## Decision

- Decompose DG06 concerns into dedicated modules:
  - `src/generation/quality_profiles_helpers.py`
  - `src/generation/quality_profiles_compile.py`
  - `src/generation/quality_profiles_apply.py`
- Convert `src/generation/quality_profiles.py` into a thin compatibility facade that re-exports:
  - `_profile_rate_triggered`
  - `_profile_clamp_probability`
  - `_profile_scalar_identity`
  - `_profile_matches_where`
  - `_default_format_error_value`
  - `_compile_data_quality_profiles`
  - `_apply_table_data_quality_profiles`
- Keep existing import paths unchanged in `src/generation/pipeline.py` and `src/generation/pipeline_orchestrator.py`.
- Extend import-contract coverage for the new DG06 modules.

## Consequences

- DG06 compile/apply logic is now concern-owned and easier to navigate.
- `quality_profiles.py` is a thin compatibility surface while behavior contracts remain unchanged.
- Generation parity, integration suites, and isolated GUI runs remained green after the decomposition.
