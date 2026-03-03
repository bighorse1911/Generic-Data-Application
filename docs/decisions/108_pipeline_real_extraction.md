# 108 - Pipeline Real Extraction

## Context

- `src/generation/pipeline.py` remained a monolithic hotspot after initial package scaffolding.
- Concern modules under `src/generation/` were still wrapper pass-throughs to `pipeline.py`.
- The project needed smaller concern-owned modules without breaking compatibility imports or deterministic generation behavior.

## Decision

- Extract real implementations from `src/generation/pipeline.py` into concern-owned modules:
  - `fk_assignment.py`
  - `scd.py`
  - `timeline.py`
  - `quality_profiles.py`
  - `locale_identity.py`
  - `profile_fit.py`
  - `correlation.py`
  - `dependency.py` (owns `_dependency_order` directly)
- Introduce:
  - `src/generation/common.py` for shared utility helpers
  - `src/generation/value_generation.py` for per-column generation helpers and column dependency ordering
  - `src/generation/pipeline_orchestrator.py` for `_generate_project_rows_internal` and parent-cache orchestration
- Reduce `src/generation/pipeline.py` to a façade that:
  - keeps public entrypoints `generate_project_rows` and `generate_project_rows_streaming`
  - re-exports legacy helper symbols for compatibility
- Add parity guardrails:
  - `tests/generation/test_pipeline_parity_contracts.py` for deterministic batch parity and streaming-vs-batch equivalence across FK/SCD/timeline/DG06/DG07/DG09/DG01 paths.

## Consequences

- Readability and navigation improve via concern-owned module boundaries.
- Legacy import contracts remain stable (`src.generator_project.*`, `src.generation.pipeline.*`, `_dependency_order` access).
- Pipeline module-size pressure is reduced, allowing removal of `src/generation/pipeline.py` from hard-size exemptions.
- Follow-up decomposition should focus on remaining large runtime/GUI modules.
