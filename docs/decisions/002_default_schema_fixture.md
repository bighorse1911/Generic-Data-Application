# Context
- Task prompt: create a default JSON schema fixture that exercises all implemented data types, generation behaviors, and generator paths, and execute it in unit tests as a regression guard.

# Decision
- Added fixture files:
  - `tests/fixtures/default_schema_project.json`
  - `tests/fixtures/city_country_pool.csv`
- Added unit test `tests/test_default_schema_fixture.py` that:
  - loads the fixture JSON through `load_project_from_json`
  - patches CSV path token to local fixture path for deterministic test execution
  - runs generation twice and asserts deterministic output
  - validates PK/FK integrity
  - validates behavior constraints across dtypes/generators (`sample_csv`, date/timestamp, latitude/longitude, distributions, `depends_on`, `null_rate`, `outlier/clamp`, `choices`, `pattern`)
- Kept production source code unchanged for safety.

# Consequences
- The repository now has a canonical, reusable schema-project fixture with broad behavior coverage.
- Test suite catches regressions in generation logic across schema JSON loading and runtime generation paths.
