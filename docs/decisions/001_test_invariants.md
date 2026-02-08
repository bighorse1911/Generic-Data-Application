# Context
- Task prompt: create `tests/test_invariants.py` with 5-10 never-break invariants covering deterministic seed behavior, PK/FK integrity, and JSON compatibility.

# Decision
- Added `tests/test_invariants.py` with 10 invariants focused on schema-project MVP guarantees:
  - deterministic output for same seed
  - output change across different seeds
  - PK non-null + uniqueness
  - FK values always present in parent table
  - single-FK per-parent cardinality bounds
  - JSON save/load roundtrip equality
  - legacy JSON defaults (`seed`, `row_count`, FK min/max)
  - SQLite insert counts match generated rows
  - validation errors include location/hint text
  - GUI screen navigation contract for home/schema_project
- Kept production code unchanged for this task.

# Consequences
- Regression coverage now captures core schema-project invariants and compatibility expectations.
- `unittest` discovery now includes a broad invariant safety net for future refactors.
