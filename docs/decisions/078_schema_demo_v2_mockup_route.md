# 078 - Add Schema Demo v2 Mockup Route

Date: 2026-02-17

## Context
- The v2 route family had no dedicated screen that mirrored the `demopage.png` mockup layout.
- Existing `schema_project_v2` focuses on canonical authoring parity and includes denser controls than the mockup.
- A low-risk experiment was requested to validate a table-centric workflow surface without changing canonical data semantics or replacing production routes.

## Decision
- Added additive route `schema_demo_v2` with strict mockup-style layout:
  - left table list and add/remove actions,
  - table-details notebook (`Columns`, `Constraints`, `Relationships`),
  - data preview panel with refresh + paging,
  - bottom actions (`Generate Data`, `Save Schema`, `Close`).
- Kept behavior fully model-backed by reusing existing schema callbacks (table/column/FK editing, validation, generation, save/load, export/SQLite).
- Added UI-only `Default Value` column rendering derived from scalar `params.default` in the columns grid (no schema model changes).
- Added `home_v2` card entry for `Schema Demo v2`.
- Added route-local first-open demo preload:
  - deterministic project with `customers`, `orders`, `products`, `shipments`,
  - `orders` selected by default,
  - deterministic generated rows preloaded for immediate preview.
- Kept route state independent from `schema_project_v2`.
- Added regression coverage in `tests/test_gui_schema_demo_v2.py` and route inventory updates in existing GUI tests.

## Consequences
- Users can test a mockup-like schema workflow without replacing or destabilizing existing v2 schema routes.
- Advanced controls remain available under constraints-tab collapsible sections, preserving functional completeness.
- Canonical data semantics and JSON compatibility remain unchanged.
- Route inventory and navigation coverage expand to include `schema_demo_v2`.

## Rollback Notes
- Remove `schema_demo_v2` route registration and Home v2 card.
- Delete `src/gui_v2_schema_demo.py` and related route-specific tests.
- No data-model migration or compatibility rollback is required.
