# Context
- Prompt requested implementing Priority 1 GUI kit modernization Phase B:
  - `TableView` large-preview path (pagination or virtualization),
  - `ColumnChooserDialog` for preview/table column visibility and order,
  - `DirtyStateGuard` pattern in `BaseScreen`,
  - `InlineValidationSummary` with quick-jump actions.
- Constraints required small safe edits, no external dependencies, and full test pass.

# Decision
- Implemented pagination as the Phase B large-preview path by extending `src/gui_kit/table.py` (`TableView.enable_pagination`, page-size controls, next/prev paging).
- Added reusable `src/gui_kit/column_chooser.py` (`ColumnChooserDialog`) and integrated it into preview authoring flow for column visibility/order control.
- Added dirty-state guard behavior directly to `src/gui_kit/layout.py` (`BaseScreen`), including unsaved indicator state and guarded discard/save prompts.
- Added `src/gui_kit/validation.py` (`InlineValidationSummary`) and integrated it into the modular schema screen with jump-to-table/column/FK actions.
- Updated `src/gui_schema_project_kit.py` integration points to use Phase B components while preserving generator/validation/IO behavior.

# Consequences
- Modular production schema screen now handles large previews with paged rendering.
- Users can adjust preview column visibility/order without mutating underlying schema order.
- Unsaved structural/project changes are surfaced and guarded during back/load navigation.
- Validation issues are now visible inline with fast jump actions to relevant editors.
- Full test suite remains green after integration.
