# 112 - Runtime Core Decomposition

## Context

- `src/performance_scaling.py` and `src/multiprocessing_runtime.py` remained runtime readability hotspots.
- Runtime behavior contracts are high-sensitivity surfaces for deterministic generation, chunk planning, fallback behavior, and run-ledger recovery.
- The refactor required strict no-behavior-change compatibility for top-level imports and GUI/runtime integration paths.

## Decision

- Decompose performance runtime into concern modules under `src/runtime/core/`:
  - `perf_types.py`
  - `perf_profile.py`
  - `perf_planning.py`
  - `perf_estimation.py`
  - `perf_execution.py`
- Decompose multiprocessing runtime into concern modules under `src/runtime/core/`:
  - `mp_types.py`
  - `mp_config.py`
  - `mp_partition.py`
  - `mp_ledger.py`
  - `mp_execution.py`
- Keep `src/performance_scaling.py` and `src/multiprocessing_runtime.py` as thin canonical facades that re-export stable symbols.
- Preserve wrapper compatibility via `src/runtime/performance.py` and `src/runtime/multiprocessing.py`.
- Update runtime import-contract tests to assert top-level and wrapper symbol parity.

## Consequences

- Runtime code ownership is now navigable by concern with reduced cognitive load in top-level modules.
- Determinism, cancellation, fallback, and ledger behavior remain parity-stable under existing tests.
- Runtime wrappers and top-level imports stay backward compatible while enabling smaller, safer future edits.
- Remaining large-module refactor focus shifts away from runtime to other hotspots.
