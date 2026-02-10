# Context

User reported `_tkinter.TclError: invalid command name` when scrolling down in the GUI, happening when already at the bottom of the page. This indicated a widget lifecycle issue, not a scrolling boundary condition.

Issue manifested at `src/gui_schema_project.py` line 124 in `ScrollableFrame._on_mousewheel()`, where the handler tried to call methods on a destroyed canvas.

# Decision

Root cause: Global event bindings registered with `bind_all()` in the `_bind_mousewheel()` method persist after the canvas widget is destroyed (e.g., when switching GUI screens). When the user scrolls after the screen is replaced, the callback fires on the destroyed widget, raising TclError.

**Smallest safe fix applied:**
- Added `winfo_exists()` guards to all four mousewheel event handlers (`_on_mousewheel`, `_on_shift_mousewheel`, `_on_linux_wheel_up`, `_on_linux_wheel_down`) to check if canvas still exists before scrolling.
- Added `winfo_exists()` guard to `_apply_zoom()` to prevent TclError when zoom events fire after destruction.

Changes made to `src/gui_schema_project.py`:
- `_on_mousewheel()`: Added `and self.canvas.winfo_exists()` check
- `_on_shift_mousewheel()`: Added `and self.canvas.winfo_exists()` check
- `_on_linux_wheel_up()`: Added conditional check
- `_on_linux_wheel_down()`: Added conditional check
- `_apply_zoom()`: Added early return if canvas doesn't exist

# Consequences

- Scrolling events that fire after the canvas is destroyed now silently exit instead of crashing with TclError.
- Zoom events (Control+MouseWheel, Control+Plus/Minus) also guard against destroyed canvas.
- User experience improves: no more exception spam when scrolling after screen navigation.
- Five new regression tests added to `tests/test_scrollable_frame_guards.py` ensure future changes don't reintroduce this class of bugs.
- All 44 existing tests continue to pass; no behavioral regressions.

## Regression tests added:
- `test_mousewheel_after_canvas_destroyed`: Mousewheel doesn't crash after destroy
- `test_shift_mousewheel_after_canvas_destroyed`: Shift+mousewheel safe after destroy
- `test_linux_wheel_events_after_canvas_destroyed`: Linux wheel events safe after destroy
- `test_zoom_after_canvas_destroyed`: Zoom methods safe after destroy
- `test_ctrl_mousewheel_after_canvas_destroyed`: Control+mousewheel safe after destroy

## Optional refactor for future consideration:

Instead of using global `bind_all()` bindings that persist, consider:
1. Binding exclusively to the canvas (not all widgets) so bindings are automatically cleaned when widget destroys.
2. Explicitly unbind handlers in a `destroy()` override or via `<Destroy>` event.
3. Store binding IDs and unbind in cleanup methods.

However, `bind_all()` is intentional here (all screens should scroll), so the `winfo_exists()` guard is the minimal, safe solution.
