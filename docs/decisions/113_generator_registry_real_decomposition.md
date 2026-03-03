# 113 - Generator Registry Real Decomposition

## Context

- `src/generation/generator_registry.py` remained the largest active readability hotspot (>1800 LOC).
- `src/generation/builtins/*` were wrapper modules only, leaving real generator behavior concentrated in one file.
- Compatibility requirements demanded no behavior changes, deterministic parity, and preserved legacy imports from `src.generators` and `src.generation.generator_registry`.

## Decision

- Extract generator registry foundations into dedicated modules:
  - `src/generation/registry_core.py` for `GenContext`, `GeneratorFn`, `REGISTRY`, `register`, and `get_generator`.
  - `src/generation/generator_state.py` for runtime cache state and `reset_runtime_generator_state`.
  - `src/generation/generator_common.py` for shared generator parse/error helpers.
- Convert `src/generation/builtins/*` into real implementation owners by concern:
  - `numeric.py`, `temporal.py`, `categorical.py`, `conditional.py`, `lifecycle.py`, `derived_expr.py`.
- Reduce `src/generation/generator_registry.py` to a compatibility facade that:
  - re-exports registry/state/helper symbols,
  - bootstraps builtin registration through an idempotent loader,
  - re-exports legacy `gen_*` function names.
- Extend compatibility tests with explicit generation-registry surface checks and generator-registry parity contracts.
- Remove `src/generation/generator_registry.py` from module-size hard exemptions once reduced below the hard cap.

## Consequences

- Generator behavior ownership is now navigable by concern while preserving legacy import/patch paths.
- Builtin registration remains deterministic and safe to invoke repeatedly through the idempotent bootstrap loader.
- `src/generation/generator_registry.py` is no longer a monolithic hotspot, reducing future change risk and review load.
- Remaining hotspot focus narrows to `src/erd_designer.py` and `src/gui/schema/editor/layout.py`.
