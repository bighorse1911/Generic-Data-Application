# Decision 101: Generator Registry Extraction (Compatibility-First)

## Context
`src/generators.py` mixed registry mechanics and generator implementations.

## Decision
Move canonical implementation to `src/generation/generator_registry.py`, add `src/generation/builtins/*` wrappers, and keep `src/generators.py` as a compatibility shim.

## Consequences
- Legacy imports remain valid.
- Future generator decomposition can proceed by concern under `src/generation/builtins/`.
