# Decision 099: Schema Layer Extraction (Compatibility-First)

## Context
`src/schema_project_model.py` mixed schema types and validation in one large module.

## Decision
Move canonical implementation to `src/schema/model_impl.py`, add `src/schema/` package API modules, and keep `src/schema_project_model.py` as a compatibility shim.

## Consequences
- Existing imports continue to work.
- New changes can target `src/schema/*` without immediate caller migration.
