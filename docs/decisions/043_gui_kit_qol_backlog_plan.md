# Context
- Prompt requested identifying additional modern GUI-kit components and quality-of-life features, then writing a concrete list/plan in `NEXT_DECISIONS.md`.
- Current toolkit includes foundational layout/form/table/scroll components but lacks some reusable UX primitives for faster authoring and lower modal friction.

# Decision
- Added a phased GUI-kit modernization backlog to `NEXT_DECISIONS.md`:
  - Phase A: reusable primitives (`ToastCenter`, `SearchEntry`, `TokenEntry`, `JsonEditorDialog`, `ShortcutManager`).
  - Phase B: high-impact authoring UX (`TableView` pagination/virtualization path, `ColumnChooserDialog`, `DirtyStateGuard`, `InlineValidationSummary`).
  - Phase C: controlled adoption strategy in app screens with incremental, test-first rollout.

# Consequences
- The roadmap now has concrete, implementable GUI-kit priorities instead of a placeholder.
- Future GUI work can be sliced safely with clear sequencing and regression control expectations.
- No runtime schema/generation behavior changed in this planning-only update.
