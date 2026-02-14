# Context
- Prompt requested implementation of Priority 1 Phase 2: time-aware constraints across validator, generation behavior, and GUI authoring controls.
- Project canon requires actionable error format, deterministic generation via seed, and decision-log updates for GUI design changes.

# Decision
- Added generator `time_offset` for row-level temporal constraints (`before`/`after`) relative to a source column in the same row.
- Added validator rules for `time_offset` covering required params, source existence, dtype match, dependency ordering, direction validity, and offset bounds.
- Exposed `time_offset` in GUI column generator selection and documented usage in the in-app generation behavior guide.
- Added tests for deterministic runtime behavior and actionable validation errors.
- Updated `PROJECT_CANON.md`, `NEXT_DECISIONS.md`, `DATA_SEMANTICS.md`, and `GUI_WIREFRAME_SCHEMA.md` to reflect Phase 2 completion and contracts.

# Consequences
- Users can now model constrained temporal relationships directly in schema authoring without external code changes.
- Invalid temporal configurations fail fast with location + issue + fix hint messages.
- Priority 1 rollout status advances to Phase 2 complete while preserving existing JSON compatibility and GUI flow behavior.
