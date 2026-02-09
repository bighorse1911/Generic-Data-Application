# Context
- Task requested implementation of Direction 3 from `NEXT_DECISIONS.md`.
- Direction 3 requires float-to-decimal migration while preserving backward compatibility and moving semantic numeric meaning into generators.

# Decision
- Implemented a safe phase slice:
- Added first-class `decimal` dtype support in validation, generation fallback, GUI dtype selection, SQL DDL mapping, and SQLite type mapping.
- Kept full backward compatibility for existing `float` schemas.
- Added semantic numeric generators `money` and `percent` to reinforce generator-based semantics.
- Added actionable validation for unsupported semantic-as-dtype values (for example `dtype="latitude"`).

# Consequences
- New projects can author decimal columns directly in GUI and JSON.
- Existing `float` projects continue to load/generate/export without changes.
- Invalid configs now provide clearer fix-oriented errors for semantic numeric misuse.
