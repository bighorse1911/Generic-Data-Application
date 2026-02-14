# Context
- Prompt requested fixing mousewheel scrolling not working in the GUI.
- Active app loads multiple screens at startup, and both modular and legacy screens register global wheel handlers.

# Decision
- Updated legacy `ScrollableFrame` wheel bindings to use additive global binds (`add="+"`) instead of overriding existing handlers.
- Added pointer-target filtering so a frame only scrolls/zooms when the mouse pointer is inside that frame.
- Reused normalized wheel delta handling for consistent scrolling behavior on Windows devices.
- Added regression tests for additive binding behavior and pointer-outside no-scroll behavior.

# Consequences
- Mousewheel scrolling works on the active screen without being hijacked by hidden screen bindings.
- Existing GUI routes remain backward compatible; no schema/generation semantics changed.
- Full unit test suite remains green after the fix.
