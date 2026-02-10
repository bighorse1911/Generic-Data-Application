# Context
- Task requested a definitive `GUI_WIREFRAME_SCHEMA.md` so GUI design decisions are captured in one authoritative document and remain reusable across GUI libraries.
- Canon and roadmap files (`PROJECT_CANON.md`, `NEXT_DECISIONS.md`) are the source of truth and must reflect this governance change.

# Decision
- Added `GUI_WIREFRAME_SCHEMA.md` at repository root as the canonical, library-agnostic GUI wireframe/decision schema.
- Included required schema concepts (`ScreenSpec`, `RegionSpec`, `ControlSpec`, `ValidationSpec`, `StateSpec`), GUI error message contract, current screen inventory baseline, cross-library mapping, and required update protocol.
- Updated `PROJECT_CANON.md` to reference the new GUI schema canon and require GUI changes to be recorded in the schema + decisions log.
- Updated `NEXT_DECISIONS.md` to mark GUI wireframe schema adoption in progress tracking.

# Consequences
- GUI design decisions now have a single authoritative home independent of Tkinter implementation details.
- Future GUI changes and GUI-library migration efforts can preserve behavior contracts with less ambiguity.
- Governance is clearer: GUI design changes must update wireframe schema and decision logs.
