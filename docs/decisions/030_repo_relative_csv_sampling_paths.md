# Context
- CSV sampling paths in fixture JSON used a machine-specific absolute path (`C:\Users\...`), which broke on cloned environments.
- The project needs path handling that works across machines and prefers repo-root-relative references.

# Decision
- Added shared path helpers in `src/project_paths.py` to:
  - resolve relative paths from repo root,
  - recover legacy absolute paths by rebasing from the `tests/...` suffix when possible,
  - normalize paths to repo-root-relative strings when inside the repo.
- Updated CSV sampling path handling in:
  - `src/schema_project_model.py` validation,
  - `src/generators.py` runtime sampling,
  - `src/schema_project_io.py` load/save normalization.
- Updated `tests/fixtures/default_schema_project.json` to use `tests/fixtures/city_country_pool.csv` instead of absolute machine paths.
- Added tests covering repo-relative validation/runtime and absolute-to-relative normalization on load/save.

# Consequences
- CSV sampling is now portable across cloned machines when files are under repo root.
- Existing legacy absolute paths continue to work where possible and are normalized to relative references in JSON IO.
- Deterministic generation and existing schema semantics remain unchanged.
