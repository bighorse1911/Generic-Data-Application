# Context
- User requested starting the Priority 1 future feature set in phased implementation.
- The smallest safe vertical slice was conditional generators (if/then), because it integrates cleanly with existing generator registry, validator flow, and GUI generator selection.

# Decision
- Implemented phase 1 as `if_then` generator support:
  - runtime generator in `src/generators.py`,
  - validator contract checks in `src/schema_project_model.py`,
  - GUI exposure by adding `if_then` to generator options.
- Added unit tests for deterministic behavior, validation guardrails, and GUI availability.
- Recorded phased rollout status in roadmap/canon docs.

# Consequences
- Project now has first Priority 1 feature implemented with deterministic behavior and actionable validation errors.
- Remaining Priority 1 items (time-aware constraints, hierarchical categories, heatmap enhancements, SCD2 non-root support) remain queued as later phases.
