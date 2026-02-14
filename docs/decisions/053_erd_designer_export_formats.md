# Context
- Prompt requested ERD export options from the new `erd_designer` GUI page, specifically JPEG, PNG, or SVG output.
- Constraints required standard-library-only implementation, Tkinter GUI integration, actionable errors, and no regressions.

# Decision
- Added ERD export support in `src/erd_designer.py`:
  - `build_erd_svg(...)` renders deterministic SVG output from ERD layout data.
  - `export_erd_file(...)` validates export path/extension and writes `.svg`, `.png`, `.jpg`, or `.jpeg`.
  - Raster export uses canvas postscript plus Ghostscript conversion with actionable error wording when prerequisites are missing.
- Updated `ERDDesignerScreen` in `src/gui_home.py`:
  - added `Export ERD...` action alongside schema load/render controls,
  - captures current ERD visibility toggles for export parity,
  - captures rendered canvas postscript for PNG/JPEG export,
  - surfaces actionable GUI errors for missing ERD/project, postscript capture failures, and write/conversion issues.
- Added ERD export unit tests in `tests/test_erd_designer.py` for:
  - SVG content generation,
  - SVG file write path,
  - unsupported extension validation,
  - PNG export prerequisite error when Ghostscript is unavailable.

# Consequences
- Users can export ERDs directly from the GUI as vector (`.svg`) or raster (`.png`/`.jpg`/`.jpeg`) assets for documentation and sharing.
- The change is additive and does not alter generation semantics, FK behavior, or schema JSON format.
- Validation failures now guide users toward concrete fixes (valid file type, render-before-export, or Ghostscript install for raster).
