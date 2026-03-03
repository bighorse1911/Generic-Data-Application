# Decision 106: Route Impl Decomposition with Patch Compatibility

## Context
`src/gui/v2/routes/_route_impl.py` had become a large mixed-concern module (route classes, shell/layout primitives, helper adapters, theme constants, and run-command integrations). This reduced navigability and made targeted edits risky.

At the same time, compatibility contracts had to remain stable:
- legacy imports from `src.gui_v2_redesign`,
- legacy module-level patch targets used by GUI tests/mocks (`run_shared_estimate`, `run_shared_build_partition_plan`, `run_shared_benchmark`, `build_profile_from_model`, `run_generation_multiprocess`, `filedialog`),
- unchanged route keys and v2 route wrapper entrypoints.

## Decision
Decompose `_route_impl.py` into route-specific and shared modules while preserving patchability:
- shared foundations:
  - `src/gui/v2/routes/theme_shared.py`
  - `src/gui/v2/routes/shell_impl.py`
  - `src/gui/v2/routes/adapters.py`
  - `src/gui/v2/routes/errors.py`
- route implementations:
  - `src/gui/v2/routes/home_impl.py`
  - `src/gui/v2/routes/schema_studio_impl.py`
  - `src/gui/v2/routes/run_center_impl.py`
  - `src/gui/v2/routes/specialists_impl.py`
- hook indirection:
  - `src/gui/v2/routes/run_hooks.py` as assignable command/filedialog hook surface
- compatibility hub:
  - `src/gui/v2/routes/_route_impl.py` reduced to thin re-exports/wiring
- shim bridge:
  - `src.gui_v2_redesign` now bridges shim-level symbols into `run_hooks` so `mock.patch("src.gui_v2_redesign.*")` continues to affect active run-center code paths.

## Consequences
- Route ownership is now explicit and easier to navigate by concern.
- `_route_impl.py` no longer contains monolithic route logic.
- Existing compatibility and patch contracts remain intact.
- Wrapper modules (`home.py`, `schema_studio.py`, `run_center.py`, `shell.py`, `erd_designer.py`, `location_selector.py`, `generation_guide.py`) remain stable entrypoints while pointing to extracted implementations.
