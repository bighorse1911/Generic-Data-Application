# Context
- Prompt requested removing dark mode and restoring the regular theme in the GUI.
- Kit screen build path was explicitly applying `apply_dark_mode(...)` during screen construction.

# Decision
- Removed forced dark mode application from `SchemaProjectDesignerKitScreen`.
- Kept a compatibility flag (`kit_dark_mode_enabled = False`) to make theme state explicit.
- Updated GUI tests to assert regular/default theme usage instead of dark palette checks.

# Consequences
- GUI now renders with the standard/default Tk/ttk theme rather than forced dark styling.
- Business logic, generation behavior, JSON IO, FK integrity, and navigation flows are unchanged.
