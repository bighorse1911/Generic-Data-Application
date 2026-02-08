# 006 - Export option dropdown (CSV/SQLite)

Date: 2026-02-08

# Context
- User requested changing export behavior so export destination is chosen from a dropdown.
- Current export UX had separate actions for CSV folder export and SQLite insert.

# Decision
- Added a readonly export dropdown in the "Generate / Preview / Export / SQLite" panel with two options:
  - `CSV (folder)`
  - `SQLite (database)`
- Replaced the dedicated CSV export button with a single `Export data` button that dispatches based on dropdown selection.
- Added `validate_export_option()` to enforce allowed options with an actionable error message that includes location and fix hint.
- Kept existing CSV export and SQLite insert handlers to minimize behavioral regression.

# Consequences
- Export UX is now extensible for future formats without adding more action buttons.
- Existing generation, FK, JSON, and SQLite logic remains unchanged.
- Added tests to cover export-option validation and GUI wiring/dispatch behavior.
