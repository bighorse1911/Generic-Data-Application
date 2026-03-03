# Decision 103: Test Layout Reorganization by Domain

## Context
Tests were in one flat directory, slowing subsystem-focused navigation.

## Decision
Reorganize tests under domain folders:
- `tests/schema/`
- `tests/generation/`
- `tests/runtime/`
- `tests/gui/`
- `tests/integration/`

Add `tests/README.md` as subsystem map.

## Consequences
- Discovery remains unchanged (`test_*.py`, recursive).
- Subsystem ownership is clearer.
