# Context
- Prompt requested implementing the previously proposed one-click `Save points CSV` flow for the Location Selector page.
- Existing page generated deterministic latitude/longitude points but required manual copy/paste from text output.

# Decision
- Added a `Save points CSV...` button to `LocationSelectorScreen`.
- The screen now stores the most recent generated sample points and writes them to a chosen file path via save dialog.
- Added reusable helpers in `src/location_selector.py`:
  - `points_to_csv_text(points)` for deterministic CSV rendering.
  - `write_points_csv(path, points)` for writing CSV output with actionable path/empty-data errors.
- Updated unit tests to cover CSV formatting, empty-data errors, and file write behavior.
- Updated canon/wireframe/roadmap docs to reflect the new action.

# Consequences
- The Location Selector workflow is now end-to-end for data generation prep: select area -> generate points -> save CSV pool for `sample_csv`.
- Users no longer need manual copying from text panels to create reusable location sample pools.
- Existing generation/navigation/IO behavior remains unchanged and regression suite remains green.
