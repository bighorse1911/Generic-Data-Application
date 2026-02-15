# Context
- Priority P1 in `NEXT_DECISIONS.md` required replacing v2 specialist bridge pages with native v2 pages while preserving canonical behavior contracts.
- Existing v2 specialist routes (`erd_designer_v2`, `location_selector_v2`, `generation_behaviors_guide_v2`) were bridge shells that redirected to classic production routes.

# Decision
- Implemented native v2 specialist pages for:
  - `erd_designer_v2`
  - `location_selector_v2`
  - `generation_behaviors_guide_v2`
- Added shared reusable tool surfaces in `src/gui_tools/` and updated classic route screens to use thin wrappers over shared tool frames.
- Added v2-native viewmodels and command adapters for specialist tool operations in `src/gui_v2/viewmodels.py` and `src/gui_v2/commands.py`.
- Kept rollback safety by retaining hidden fallback routes:
  - `erd_designer_v2_bridge`
  - `location_selector_v2_bridge`
  - `generation_behaviors_guide_v2_bridge`
- Updated canon documentation (`GUI_WIREFRAME_SCHEMA.md`, `PROJECT_CANON.md`, `NEXT_DECISIONS.md`) to mark P1 complete and document native-route + rollback-route contracts.

# Consequences
- v2 specialist routes are now native destinations instead of launch-through bridge pages.
- Classic routes remain available and behavior-compatible.
- Rollback remains low-risk via hidden bridge routes for one release cycle.
- Future work (P2+) can proceed without route-fragmentation debt from specialist v2 bridges.
