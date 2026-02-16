# 077 - Restore And Reimplement Specialist V2 Pages

Date: 2026-02-16

## Context
- The v2 route set expanded in P9, which increased the number of cards on `home_v2`.
- `home_v2` card layout was non-scrollable, so lower cards could become effectively unreachable on default window sizes.
- Reported impact: `erd_designer_v2` and `location_selector_v2` appeared missing from the v2 experience.

## Decision
- Kept specialist native v2 routes (`erd_designer_v2`, `location_selector_v2`) and reimplemented access/entry ergonomics:
  - `home_v2` now uses a scrollable cards region so all v2 routes remain reachable.
  - `ERDDesignerV2Screen` now exposes explicit `Open Classic Tool` header action to `erd_designer`.
  - `LocationSelectorV2Screen` now exposes explicit `Open Classic Tool` header action to `location_selector`.
- Added regression coverage:
  - `tests/test_gui_v2_native_tools.py`
    - validates `home_v2` card region is scrollable and includes specialist v2 cards.
    - validates specialist v2 screens expose `Open Classic Tool` actions.

## Consequences
- Specialist v2 pages are reliably discoverable and accessible even as v2 route inventory grows.
- Rollback path remains explicit and user-visible from specialist v2 routes.
- No runtime/data semantics changed; this is GUI navigation/UX hardening only.

## Rollback Notes
- Reverting this change only requires restoring non-scroll card layout and removing `Open Classic Tool` header actions.
- Classic specialist routes remain unchanged and available.
