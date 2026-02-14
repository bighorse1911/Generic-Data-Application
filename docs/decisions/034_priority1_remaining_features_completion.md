# Context
- Prompt requested implementation of remaining Priority 1 features:
  - hierarchical categories,
  - validation heatmap enhancements,
  - SCD2 support beyond root tables (incoming-FK child tables).
- Canon constraints require deterministic generation, actionable validation messages, GUI availability where applicable, and updated decision/canon docs.

# Decision
- Added `hierarchical_category` generator with validator/runtime guardrails and GUI authoring exposure.
- Enhanced validation heatmap logic with richer issue extraction and explicit buckets: `Dependencies` and `SCD/BK` (in addition to existing buckets).
- Removed SCD2 root-table-only validator restriction and added FK-capacity-aware child-table SCD2 version growth in runtime generation.
- Added/updated unit tests for all three feature areas and updated canonical docs (`PROJECT_CANON.md`, `NEXT_DECISIONS.md`, `DATA_SEMANTICS.md`, `GUI_WIREFRAME_SCHEMA.md`).

# Consequences
- Users can author hierarchical category columns directly from GUI generator controls.
- Validation heatmap now surfaces dependency and SCD/business-key problems with clearer per-table localization.
- SCD2 can now be enabled on child tables while preserving FK integrity and respecting FK max-children capacity during version expansion.
