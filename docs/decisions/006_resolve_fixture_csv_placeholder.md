# 006 — Resolve fixture CSV placeholder on load

Date: 2026-02-08

Summary
- When loading a project JSON that uses the placeholder `__CITY_COUNTRY_CSV__`, automatically resolve it to the bundled `tests/fixtures/city_country_pool.csv` if that file exists in the repository. This mirrors the behavior used in unit tests and makes the default fixture usable from the GUI without manual edits.

Decision
- Modify `load_project_from_json()` to detect the placeholder and replace it with the path to the local fixture when available.

Consequences
- Users loading the included default fixture can generate sample data immediately without editing JSON.
- This is a targeted convenience for the shipped fixture; future placeholders should be handled explicitly or via a more general variable-substitution mechanism.
