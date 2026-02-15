# Context
- Task request: add ERD-page authoring so users can create a new schema directly in `erd_designer`, then add tables, columns (including dtype/PK), and relationships.
- Existing ERD page supported JSON load/render, draggable layout, and export but had no in-page schema mutation controls.
- Canon requires actionable GUI validation errors and low-risk additive changes.

# Decision
- Added pure helper functions in `src/erd_designer.py` for ERD-specific schema authoring:
  - `new_erd_schema_project(...)`
  - `add_table_to_erd_project(...)`
  - `add_column_to_erd_project(...)`
  - `add_relationship_to_erd_project(...)`
- Added a new "Schema authoring" panel in `ERDDesignerScreen` (`src/gui_home.py`) with controls for:
  - new schema creation (name + seed),
  - table creation (name + row count),
  - column creation (table + name + dtype + PK + nullable),
  - relationship creation (child/parent mapping + min/max children).
- Kept all validation messages in canonical actionable format: `ERD Designer / <Location>: <issue>. Fix: <hint>.`
- Added/updated tests in `tests/test_erd_designer.py` and `tests/test_invariants.py`.

# Consequences
- ERD designer can now be used as a lightweight schema sketching/editor surface without leaving the page.
- Existing ERD render/export/navigation behavior remains intact, with full regression suite passing.
- JSON IO and backend generation paths remain unchanged; this is an additive GUI + helper-layer capability.
