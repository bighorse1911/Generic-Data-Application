# Decision 100: Generation Pipeline Extraction (Compatibility-First)

## Context
`src/generator_project.py` had high cognitive load and internal helper coupling.

## Decision
Move canonical implementation to `src/generation/pipeline.py`, add `src/generation/dependency.py`, and keep `src/generator_project.py` as a compatibility shim.

## Consequences
- Backward imports remain stable.
- Storage/runtime code can use `src.generation.dependency.dependency_order` instead of internal helper coupling.
