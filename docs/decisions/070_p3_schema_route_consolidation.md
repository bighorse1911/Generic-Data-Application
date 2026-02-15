# Context
- Priority P3 in `NEXT_DECISIONS.md` required consolidating schema authoring routes and defining a controlled deprecation path for `schema_project_legacy`.
- Route topology still exposed multiple schema authoring entry points (`schema_project`, `schema_project_kit`, `schema_project_legacy`) in primary navigation, creating drift risk.

# Decision
- Consolidated primary schema authoring UX to `schema_project` only.
- Added shared route-policy constants in `src/gui_route_policy.py`:
  - `SCHEMA_PRIMARY_ROUTE`
  - `SCHEMA_FALLBACK_ROUTES`
  - `SCHEMA_DEPRECATED_ROUTES`
- Updated app route map in `src/gui_home.py`:
  - `schema_project` and `schema_project_kit` now map to the same `SchemaProjectDesignerKitScreen` instance.
  - `schema_project_legacy` remains a separate rollback route via `SchemaProjectLegacyFallbackScreen`.
- Added optional `on_show()` lifecycle hook invocation in `App.show_screen()`.
- Updated Home and `schema_studio_v2` to remove primary navigation entry points to fallback schema routes.
- Added non-blocking deprecation status messaging when `schema_project_legacy` is shown.
- Added parity/consolidation tests:
  - `tests/test_schema_route_consolidation.py`
  - `tests/test_schema_route_parity.py`
- Updated canonical docs to encode one-cycle hidden fallback/deprecation policy.

# Consequences
- Schema authoring route drift is reduced by consolidating primary navigation to one route.
- Rollback safety is preserved for one release cycle through hidden fallback routes.
- `schema_project_legacy` remains functional but explicitly deprecated and non-primary.
- Next release-cycle removal can proceed if parity/rollback gates remain green.
