# Context
- Prompt requested implementing Priority 1 GUI kit modernization phase A:
  - `ToastCenter`
  - `SearchEntry` (deterministic debounce)
  - `TokenEntry`
  - `JsonEditorDialog`
  - `ShortcutManager`
- Requirement included making new behavior accessible in the GUI and keeping tests green.

# Decision
- Added phase-A primitives in `src/gui_kit` as reusable modules and exported them through `src/gui_kit/__init__.py` component catalog.
- Integrated phase-A primitives into `SchemaProjectDesignerKitScreen`:
  - non-blocking toasts for key success paths,
  - debounced search controls for tables/columns/FKs,
  - token editors for business-key/static/changing/tracked comma-separated fields,
  - params JSON editor dialog with pretty-format/apply flow,
  - centralized keyboard shortcuts and shortcuts help dialog.
- Added focused tests for new kit primitives and updated catalog expectations.

# Consequences
- Modular production schema screen now has lower-friction authoring and navigation QoL features without changing backend generation semantics.
- GUI-kit now has richer reusable primitives for future screens and migration slices.
- Full test suite remains green after integration.
