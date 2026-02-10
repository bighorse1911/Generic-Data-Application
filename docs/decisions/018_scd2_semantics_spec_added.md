# Context
- Task requested adding Slowly Changing Dimension Type 2 (SCD2) to canonical semantics, explicitly as not yet implemented in the application.
- Required scope: authoritative docs should capture business active time periods (`date` or `datetime`), business-key linkage, and configurable slowly-changing columns.

# Decision
- Added canonical SCD2 semantics to `DATA_SEMANTICS.md`:
  - defined SCD2 behavior and constraints,
  - documented active-period rules (`date`/`datetime`),
  - documented business-key-linked multi-row history behavior,
  - documented tracked slowly-changing columns semantics,
  - added future validation error examples and implementation-pending status.
- Updated `PROJECT_CANON.md` to reference SCD2 semantics as defined-but-not-implemented.
- Updated `NEXT_DECISIONS.md` to track SCD2 semantics adoption and add SCD2 phase-1 implementation as a future feature candidate.
- Updated `GUI_WIREFRAME_SCHEMA.md` to note SCD2 GUI controls are future work.

# Consequences
- SCD2 semantics now have an authoritative contract without introducing runtime or GUI regressions.
- Future implementation work has a clearer target contract for validation, JSON shape, and GUI authoring.
- Current app behavior remains unchanged until explicit implementation phases are started.
