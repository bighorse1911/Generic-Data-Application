# Context
- Generation failed with traceback ending in `KeyError: 'path'` from `gen_sample_csv` when running a GUI-authored project.
- The failing configuration had `generator="sample_csv"` with missing/empty `params.path`.

# Decision
- Added validation guardrails in `validate_project()` for `sample_csv` columns:
  - require `params.path`,
  - require `params.column_index` to be an integer `>= 0`,
  - require `params.path` to point to an existing file,
  - require `params` to be an object when provided.
- Added defensive runtime guard in `generator_project._gen_value()` to translate generator `KeyError` into actionable `ValueError` with table/column location.
- Hardened `generators.gen_sample_csv()` with explicit validation and actionable error messages (instead of raw key/index conversion failures).
- Added focused regression tests for missing `sample_csv` path validation and generator-level error messaging.
- Updated fixture/test alignment for the GUI-extended default schema:
  - fixed invalid `SCD_TEST.PK` generator assignment (`sample_csv` -> `null`),
  - made default fixture test assert required core tables are present (subset), allowing additive fixture tables.

# Consequences
- Invalid `sample_csv` config now fails fast with clear fix hints instead of a traceback.
- GUI generation path now surfaces actionable validation errors for this class of misconfiguration.
- Full test suite remains green with the updated fixture shape.
