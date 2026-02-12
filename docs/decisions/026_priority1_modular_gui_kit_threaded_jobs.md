# Context
- Priority 1 in `NEXT_DECISIONS.md` for modular GUI migration needed an explicit update and concrete progress.
- `schema_project_kit` already used `FormBuilder` and `TableView`, but long-running actions still followed legacy thread wiring rather than the `BaseScreen.safe_threaded_job` pattern called out in project canon.

# Decision
- Updated `SchemaProjectDesignerKitScreen` to route long-running actions through `BaseScreen.safe_threaded_job`:
  - generate all tables,
  - generate sample,
  - SQLite create/insert.
- Added a GUI regression test to verify kit long-running actions invoke `safe_threaded_job`.
- Updated `NEXT_DECISIONS.md` Priority 1 section to reflect completed slice-level progress and remaining work.
- Updated `GUI_WIREFRAME_SCHEMA.md` to record the long-running-action behavior contract for `schema_project_kit`.

# Consequences
- Kit preview path now consistently uses the reusable `gui_kit` background-job pattern.
- Busy/progress and duplicate-trigger behavior remains consistent while reducing custom thread wiring in the modular screen.
- Roadmap and wireframe docs now explicitly reflect this Priority 1 progress.
