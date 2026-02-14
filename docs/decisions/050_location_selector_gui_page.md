# Context
- Prompt requested a new GUI page named `Location Selector` that allows map interaction (zoom/pan), center-point selection, radius selection, GeoJSON creation, and deterministic latitude/longitude sampling within that radius.
- Constraints required Tkinter + standard library only, actionable errors, no regressions, and incremental low-risk implementation.

# Decision
- Added a new Home route `location_selector` and implemented `LocationSelectorScreen` in `src/gui_home.py`.
- Added map-centric UI behavior using Tkinter canvas only:
  - click-to-select center point,
  - zoom in/out (buttons + wheel),
  - pan (drag),
  - reset view.
- Added deterministic geospatial utilities in new module `src/location_selector.py`:
  - center/radius validation with actionable errors,
  - circle polygon/GeoJSON generation,
  - deterministic sample point generation inside circle from seed.
- Added tests for:
  - GeoJSON shape correctness and closure,
  - deterministic and bounded sample generation,
  - actionable validation errors,
  - GUI navigation route contract for `location_selector`.
- Updated canonical docs to record new GUI route and behavior contract.

# Consequences
- Users now have an in-app geographic authoring tool that creates a reusable radius-based GeoJSON and deterministic lat/lon samples without external dependencies.
- This creates a concrete base for future schema/generator integrations involving geographic regions.
- Existing schema generation, FK integrity, JSON IO, and GUI navigation behavior remains intact under full test run.
