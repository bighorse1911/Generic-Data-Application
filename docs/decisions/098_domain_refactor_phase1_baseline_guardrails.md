# Decision 098: Domain-First Refactor Phase 1 (Baseline + Guardrails)

## Context
The codebase accumulated large top-level modules and a flat test layout, making navigation harder for both humans and agents.

## Decision
Introduce a domain-first package scaffold and add guardrails:
- `docs/ARCHITECTURE_INDEX.md`
- `tests/test_import_contracts.py`
- `tests/test_module_size_budget.py`

## Consequences
- Navigation improves immediately.
- Import compatibility is now explicitly tested.
- Module-size drift is constrained for future edits.
