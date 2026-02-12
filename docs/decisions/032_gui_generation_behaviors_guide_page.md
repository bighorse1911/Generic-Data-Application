# Context
- User requested a new GUI page that explains every supported type of data generation behavior and how to use each one.
- The change needed to stay low-risk: no generator runtime changes, no schema contract changes, and no regressions in existing GUI routes.

# Decision
- Added a new read-only route and screen: `generation_behaviors_guide`.
- Wired the screen into Home navigation so users can open it directly from the app entry page.
- Implemented a scrollable set of behavior cards with two fields per behavior:
  - what it does,
  - how to configure it in the current workflow (GUI fields and/or JSON when advanced).
- Updated GUI navigation invariant tests to assert:
  - the new route exists,
  - the screen type is registered,
  - key behavior entries (`sample_csv`, `if_then`, `Business key + SCD`) are present.
- Updated canon docs (`PROJECT_CANON.md`, `NEXT_DECISIONS.md`, `DATA_SEMANTICS.md`, `GUI_WIREFRAME_SCHEMA.md`) to record the new screen contract.

# Consequences
- Users now have an in-app reference page for data-generation behaviors without leaving the GUI.
- No changes to generation logic or JSON schema semantics were introduced.
- Navigation contract coverage now protects the new route against accidental removal.
