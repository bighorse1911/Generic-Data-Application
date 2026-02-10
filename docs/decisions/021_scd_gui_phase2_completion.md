# Context
- Task requested fully implementing SCD and Business Key logic in both GUI screens, removing the related item from `NEXT_DECISIONS.md` In Progress, and updating the example JSON schema.
- Backend/runtime support for SCD1/SCD2 was already present; GUI authoring/editing controls were the remaining gap.

# Decision
- Implemented table-level SCD/business-key authoring in both schema designer screens:
  - `src/gui_schema_project.py` (legacy screen),
  - `src/gui_schema_project_kit.py` (kit preview screen).
- Added GUI bindings for:
  - `business_key` (comma-separated columns),
  - `scd_mode` (`scd1` / `scd2`),
  - `scd_tracked_columns` (comma-separated),
  - `scd_active_from_column`,
  - `scd_active_to_column`.
- Updated GUI apply/load flows so these fields roundtrip between editor controls and `TableSpec`.
- Updated all `TableSpec` rebuild call sites in GUI table/column edit flows to preserve SCD/business-key fields (prevents accidental config loss after column edits or sample-project creation).
- Added targeted GUI tests covering both screens and SCD field persistence.
- Updated example schema fixture (`tests/fixtures/default_schema_project.json`) with a minimal SCD/business-key table configuration.
- Updated authoritative docs (`PROJECT_CANON.md`, `NEXT_DECISIONS.md`, `DATA_SEMANTICS.md`, `GUI_WIREFRAME_SCHEMA.md`) to mark SCD GUI controls as implemented and remove stale "pending" language.

# Consequences
- SCD authoring is now available in both GUI screens with parity.
- Existing behavior (generation/FK/JSON/GUI navigation) remains intact while preserving backward compatibility.
- Roadmap and canon docs now consistently reflect that SCD phase 2 GUI controls are complete, with root-table-only SCD2 scope still explicitly documented.
