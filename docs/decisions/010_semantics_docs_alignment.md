# Context
- Prompt requested review of `PROJECT_CANON.md`, `NEXT_DECISIONS.md`, and new `DATA_SEMANTICS.md`, with updates only if justified.
- Found mismatch: runtime still uses `float` while semantics/canon text implied decimal-only completion, plus readability issues from encoding artifacts.

# Decision
- Updated `DATA_SEMANTICS.md` to clean encoding artifacts and document explicit migration status:
- Current runtime compatibility (`float`) preserved.
- Direction 3 target (`decimal` and `bytes`) retained as canonical direction.
- Updated `PROJECT_CANON.md` and `NEXT_DECISIONS.md` to align on the same migration framing and immediate roadmap items.

# Consequences
- Documentation now matches both current runtime behavior and intended roadmap.
- Contributors can implement Direction 3 incrementally without breaking JSON backward compatibility assumptions.
