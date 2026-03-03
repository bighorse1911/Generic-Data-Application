# Decision 107: Real Schema Validator Extraction from `model_impl.py`

## Context
`src/schema/model_impl.py` had accumulated a monolithic `validate_project` implementation (~3245 lines) even after introducing `src/schema/validators/*` as package scaffolding.  
Validator modules were still wrappers, which made validation logic hard to navigate and increased change risk.

## Decision
Extract validation concerns into real validator modules and make `src/schema/validate.py` the canonical orchestrator:
- `src/schema/validators/generators.py` for core project/table/column/generator checks (including per-table correlation/SCD ordering hooks),
- `src/schema/validators/correlation.py` for correlation matrix/group validation helpers,
- `src/schema/validators/scd.py` for business-key/SCD rules,
- `src/schema/validators/fk.py` for FK integrity and FK profile contracts,
- `src/schema/validators/timeline.py` for DG03 timeline constraints,
- `src/schema/validators/quality_profile_fit.py` for DG06 + DG07 validation,
- `src/schema/validators/locale.py` for DG09 locale bundle validation,
- `src/schema/validators/common.py` for shared parsing/error helpers.

`src/schema/model_impl.py` is reduced to schema dataclasses/constants and thin compatibility wrappers so legacy imports continue to work.

## Consequences
- Validation ownership is now domain-by-concern instead of one monolithic function.
- Public import contracts remain stable (`src.schema_project_model.validate_project`, `src.schema.validate.validate_project`, `correlation_cholesky_lower`).
- Added parity guardrails via `tests/schema/test_validation_parity_contracts.py` for exact error text and first-failure precedence.
- `tests/test_module_size_budget.py` no longer needs a hard exemption for `src/schema/model_impl.py` after slimming.
