# Context
- User requested to continue implementing Deferred Feature A (Performance scaling) after phase-1 profile/estimate delivery.
- Existing roadmap phases required progression toward runtime-safe planning while keeping changes small and testable.

# Decision
- Implemented phase-1B chunk planning in the performance-scaling slice:
  - Added FK-stage-aware deterministic chunk plan logic in `src/performance_scaling.py` via `build_chunk_plan` and `summarize_chunk_plan`.
  - Added dependency-cycle detection for selected-table FK graphs with actionable `Performance Workbench / Chunk plan ... Fix: ...` errors.
  - Extended `performance_workbench` UI with a `Build chunk plan` action and a chunk-plan preview grid.
  - Added tests for chunk-plan determinism, stage ordering, range calculation, summary totals, and cycle guardrails.

# Consequences
- Users can now inspect deterministic table chunk boundaries and FK execution stages before runtime implementation.
- Validation now catches cyclic selected-table dependencies early in planning flows.
- This continues incremental delivery without changing core generation semantics or JSON compatibility.
