# Context
- Task requested adding SCD1 as an option alongside already documented SCD2 semantics.
- Scope remained documentation-only: define canonical behavior and keep runtime/GUI marked as not yet implemented.

# Decision
- Added SCD1 canonical semantics to `DATA_SEMANTICS.md`:
  - SCD1 linked to business key,
  - overwrite-in-place behavior for tracked slowly-changing columns,
  - no historical row versions,
  - one-row-per-business-key rule with actionable future validation examples.
- Renumbered SCD2 section to follow SCD1 and kept SCD2 semantics intact.
- Updated `PROJECT_CANON.md`, `NEXT_DECISIONS.md`, and `GUI_WIREFRAME_SCHEMA.md` to refer to both SCD1 and SCD2 options as defined semantics with implementation pending.

# Consequences
- Canonical docs now describe multiple SCD options (`scd1`, `scd2`) consistently.
- Future implementation work can proceed with a clear semantic contract for both overwrite and history modes.
- No runtime behavior changed in the current application.
