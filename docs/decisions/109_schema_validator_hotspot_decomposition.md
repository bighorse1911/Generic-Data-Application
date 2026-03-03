# 109 - Schema Validator Hotspot Decomposition

## Context

- `src/schema/validators/generators.py` and `src/schema/validators/quality_profile_fit.py` were large readability hotspots.
- Validation order and error-text contracts are high-sensitivity compatibility surfaces.
- The refactor needed to improve navigation without changing behavior.

## Decision

- Decompose `src/schema/validators/generators.py` into concern modules:
  - `project_table_rules.py` for project/table/column structural validation
  - `generator_param_parsing.py` for shared generator parse helpers
  - `generator_rules_numeric.py` for numeric/categorical generator rules
  - `generator_rules_dependency.py` for dependency-driven generator rules
- Keep `generators.py` as strict-order orchestration + compatibility surface.
- Decompose `src/schema/validators/quality_profile_fit.py` into:
  - `dg06_quality_profiles.py` for DG06 validation
  - `dg07_sample_profile_fit.py` for DG07 validation
- Keep `quality_profile_fit.py` as compatibility re-export hub.

## Consequences

- Validator logic is easier to navigate by concern while preserving import contracts.
- First-failure precedence and error message text remain stable.
- Schema validator module-size pressure is reduced.
- Next decomposition focus shifts to remaining large GUI/runtime modules.
