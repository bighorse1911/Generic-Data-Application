# 005 — Guard duplicate generator registrations

Date: 2026-02-08

Summary
- Add a guard in the `register()` decorator to raise an error when a generator name is registered more than once. This prevents accidental overwrites and subtle behavioral regressions.

Decision
- `register()` will now raise `KeyError` if the provided name already exists in the registry. Tests were added to assert this behavior.

Consequences
- Prevents accidental replacement of generators (was the root cause of the duplicated `normal` generator bug).
- Slight breaking change for code that intentionally re-registers names; such code must now explicitly remove the old entry.
