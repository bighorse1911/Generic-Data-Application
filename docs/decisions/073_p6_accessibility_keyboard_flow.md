# 073 - P6 Accessibility And Keyboard Flow Pass

Date: 2026-02-16

## Context
- Core interactive routes had uneven keyboard discoverability and no consistent route-scoped shortcut lifecycle.
- Focus traversal across major sections was implicit and screen-specific, which made power-user flows inconsistent.
- Dense Treeview-backed tables already supported copy/recovery basics, but lacked standardized multi-row and paging ergonomics.
- Hidden rollback route `schema_project_legacy` needed parity for release-safety fallback.

## Decision
- Added route lifecycle support in `App.show_screen()` to call `on_hide()` for the outgoing screen and `on_show()` for the incoming screen, while skipping hide/show churn when both route keys map to the same frame instance.
- Standardized route-scoped shortcut management on:
  - `schema_project`
  - `schema_project_legacy`
  - `performance_workbench`
  - `execution_orchestrator`
  - `run_center_v2`
- Added focus-anchor traversal contracts using `FocusController` with:
  - resilient next/previous cycling (`F6` / `Shift+F6`)
  - viewability-aware skip behavior
  - separate default vs last-focused anchor tracking.
- Extended `ShortcutManager` with:
  - `register_help_item(sequence, description)` for discoverability-only entries
  - `is_active` property for lifecycle assertions.
- Expanded shared Treeview keyboard ergonomics (non-destructive):
  - `Ctrl/Cmd+A` select all
  - `Ctrl/Cmd+Shift+C` copy without headers
  - `PageUp/PageDown` page-step navigation
  - `Ctrl/Cmd+Home` / `Ctrl/Cmd+End` endpoint jumps.
- Applied shared table keyboard support to inline validation tables and legacy schema tables for parity.

## Consequences
- Keyboard shortcuts are active only for the visible route, reducing cross-screen collisions.
- Focus traversal is now explicit, predictable, and resilient when panels are collapsed/hidden.
- Dense table interactions are faster for power users while remaining non-destructive.
- Legacy rollback route remains behaviorally aligned with primary schema authoring for keyboard/focus flows.
- Added regression tests for focus controller behavior, shortcut lifecycle/discoverability, table keyboard support, and route activation/deactivation contracts.
