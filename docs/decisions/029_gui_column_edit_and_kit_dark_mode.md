# Context
- The GUI needed two usability updates: edit existing table columns in-place, and add a dark mode for kit-based screens that is visibly applied to the page.
- Changes had to remain low-risk and preserve existing schema/generation behavior and JSON compatibility.

# Decision
- Added selected-column edit behavior to schema designer screens by:
  - loading selected column values into the existing column editor form,
  - adding an "Apply edits to selected column" action,
  - validating edits through existing project validation before apply.
- Added a shared gui_kit dark mode helper (`src/gui_kit/theme.py`) and applied it in `SchemaProjectDesignerKitScreen` during build.
- Added GUI tests for selected-column editing and dark mode application.

# Consequences
- Users can now modify column definitions without delete/re-add workflows.
- Kit screens render using a consistent dark palette, including ttk and tk widgets used in modular pages.
- Validation and error messaging remain actionable (`Location / issue / Fix`), and full tests remain green.
