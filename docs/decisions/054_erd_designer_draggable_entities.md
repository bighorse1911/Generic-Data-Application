# Context
- Prompt requested ERD page support for moving entities (tables) while keeping relationships connected automatically.
- Constraints required standard-library-only Tkinter implementation, small safe edits, and no regressions.

# Decision
- Added draggable ERD table behavior in `ERDDesignerScreen`:
  - click/drag on table node moves its canvas position,
  - moved positions are tracked per table,
  - relationship lines and labels are recalculated from moved nodes on redraw.
- Added reusable ERD layout helpers in `src/erd_designer.py`:
  - `apply_node_position_overrides(...)` to merge interactive positions into computed layout,
  - `compute_diagram_size(...)` to expand scroll bounds for moved nodes.
- Updated SVG export path so `build_erd_svg(...)` accepts optional node positions and exports the current interactive arrangement.
- Added unit tests covering node position overrides, diagram-size expansion, and SVG position override behavior.

# Consequences
- Users can rearrange ERD entities interactively to improve readability while relationship routing stays correct.
- Exported SVG diagrams now match the adjusted on-screen layout.
- Changes are additive and do not alter schema semantics, generation logic, FK integrity, or JSON project contracts.
