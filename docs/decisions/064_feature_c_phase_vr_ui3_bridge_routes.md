# Context
- Prompt requested: "Continue with Deferred Feature C - Full visual redesign."
- Feature C roadmap called for the next UI phase to expand parity routes while keeping rollout additive and low-risk.

# Decision
- Implemented VR-UI-3 bridge-route slice:
  - added reusable `ToolBridgeV2Screen` shell in `src/gui_v2_redesign.py`,
  - added additive v2 bridge routes/screens: `erd_designer_v2`, `location_selector_v2`, `generation_behaviors_guide_v2`,
  - updated `home_v2` cards and `App` route registration to include new v2 bridge routes,
  - expanded GUI navigation invariants to assert route presence, type contracts, and basic screen attributes.
- Updated canon/docs to reflect the new v2 bridge route inventory and Feature C progress state.

# Consequences
- Feature C now has broader route-level parity under the redesign shell without changing runtime semantics.
- Existing production tools (`erd_designer`, `location_selector`, `generation_behaviors_guide`) remain the behavior source of truth.
- Next phases can migrate tool internals into native v2 layouts incrementally while preserving safe fallback routes.
