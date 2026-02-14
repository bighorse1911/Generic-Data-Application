# Context
- Prompt requested implementing Priority 1 Phase C adoption in `schema_project_legacy`:
  - preview pagination (opt-in),
  - preview column chooser,
  - dirty-state prompts,
  - inline validation summary quick-jumps.
- Constraints required low-risk migration slices, deterministic behavior preservation, and full test pass.

# Decision
- Integrated Phase B components into legacy screen with minimal business-logic impact:
  - replaced legacy preview tree wrapper with `TableView` and added opt-in pagination controls,
  - added `ColumnChooserDialog` for preview column visibility/order without mutating schema order,
  - added `InlineValidationSummary` panel and table/column/FK quick-jump handlers,
  - added legacy dirty-state guard (`unsaved` indicator + back/load save/discard/cancel prompts).
- Kept heavy preview paging path opt-in (`Use paged preview`) to preserve baseline behavior unless enabled.
- Added focused legacy Phase C tests and kept existing regression suites intact.

# Consequences
- `schema_project_legacy` now has parity for key Phase B authoring UX features while remaining fallback-compatible.
- Generation, FK integrity, JSON IO, and navigation behavior remain stable with full test-suite pass.
- Canonical docs and roadmap now reflect that Phase C legacy adoption slice is completed.
