# Context
- Task requested continuing Direction 3.
- `NEXT_DECISIONS.md` listed Phase 3 as migrating default fixtures/templates from `float` to `decimal`, while keeping legacy compatibility.

# Decision
- Migrated `tests/fixtures/default_schema_project.json` numeric non-integer dtypes from `float` to `decimal`.
- Rebuilt the fixture `sql_ddl` field to match new decimal mappings.
- Added GUI validation warning for legacy float columns with a clear migration fix hint.
- Added/updated tests to enforce:
- fixture uses decimal and no float dtypes,
- GUI surfaces float deprecation warning,
- existing legacy float runtime compatibility remains intact.

# Consequences
- Default schema fixture now reflects Direction 3 canonical authoring.
- Legacy `float` schemas still load/generate/export.
- GUI users get actionable guidance toward `decimal` without a breaking change.
