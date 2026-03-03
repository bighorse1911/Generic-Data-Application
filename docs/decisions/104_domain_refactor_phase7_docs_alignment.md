# Decision 104: Canon and Roadmap Documentation Alignment for Domain-First Refactor

## Context
Project-level architecture and roadmap docs must remain authoritative after structural refactors.

## Decision
Update:
- `PROJECT_CANON.md` to document domain-first package scaffolding and compatibility shims.
- `NEXT_DECISIONS.md` to mark the refactor stream as active with completed and follow-up slices.

## Consequences
- Canon and roadmap now reflect the current code layout.
- Future contributors can track remaining decomposition work without inferring from git history.
