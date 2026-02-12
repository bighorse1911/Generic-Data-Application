# Context
- Priority 1 in `NEXT_DECISIONS.md` required completing modular GUI migration and full parity for the production `schema_project` route.
- Before this change, production still pointed to the legacy screen while modular behavior lived on additive kit routes.

# Decision
- Switched `schema_project` production routing in `src/gui_home.py` to `SchemaProjectDesignerKitScreen`.
- Preserved fallback safety by adding `schema_project_legacy` route for the legacy screen.
- Kept `schema_project_kit` route available as a modular parity/reference route.
- Added regression assertions that production routing uses the modular screen.
- Updated roadmap/canon docs to reflect completion of Priority 1 modular migration.

# Consequences
- Production GUI path now uses `gui_kit` composition (`BaseScreen`, `FormBuilder`, `TableView`, `safe_threaded_job`).
- Legacy UI remains accessible for low-risk fallback during transition.
- Navigation, generation, FK integrity, and JSON IO behavior remain compatible; full tests remain green.
