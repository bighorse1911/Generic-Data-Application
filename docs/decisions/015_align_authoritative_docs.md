# Context

User requested a disciplined pair-programming review of the four authoritative documents (PROJECT_CANON.md, NEXT_DECISIONS.md, DATA_SEMANTICS.md, GUI_WIREFRAME_SCHEMA.md) for inconsistencies and misalignment.

Review identified five gaps:
1. Float deprecation stated inconsistently across docs (soft deprecation vs. hard runtime block)
2. Decimal adoption claimed complete but not formalized in GUI wireframe schema
3. Validation error format mismatch (DATA_SEMANTICS uses one shape; GUI_WIREFRAME_SCHEMA uses similar but different)
4. Direction 3 status marked "completed" but phrased as ongoing work
5. Next Candidates listed without priority/sequencing, including the error-format alignment task

# Decision

Applied surgical changes to align all four documents:

1. **PROJECT_CANON.md**: Clarified float deprecation as **runtime blocking policy** (GUI rejects new float columns via validation), not vague soft deprecation. Emphasized legacy JSON float backward compatibility. Updated validation section to reference canonical error format contract.

2. **GUI_WIREFRAME_SCHEMA.md**: Added formal section 3.1 enumerating canonical GUI dtypes (`int`, `decimal`, `text`, `bool`, `date`, `datetime` with `bytes` roadmap). Clarified float as legacy-only with runtime deprecation. Renamed section 3 to "Canonical Data Types and Validation Error Contract" and unified error format examples with DATA_SEMANTICS.md.

3. **NEXT_DECISIONS.md**: 
   - Clarified Direction 3 is "completed" (not ongoing) and added explicit policy statement: "GUI now blocks new `float` authoring (runtime validation) while preserving legacy JSON load/generate/export compatibility."
   - Reorganized Next Candidates into Priority 1/2/3 tiers
   - **Priority 1** (unblocks others): validator error wording alignment to canonical format (this is the error-format unification task)
   - **Priority 2**: GUI kit migration in small slices
   - **Priority 3**: Future features (conditional generators, time-aware constraints, etc.)

4. **DATA_SEMANTICS.md**: No changes required; it is already authoritative and correctly specifies the canonical error format and float backward-compatibility policy.

# Consequences

- All four documents now use consistent terminology: 
  - Float is **legacy compatibility** (accepted at load, blocked at GUI creation, fully functional at runtime).
  - Error format is unified: `<Location>: <issue>. Fix: <hint>.`
  - Canonical dtypes are formally listed in both PROJECT_CANON and GUI_WIREFRAME_SCHEMA.

- Direction 3 status is now unambiguous: complete with active maintenance (float compatibility tests required).

- Next Candidates are now prioritized, enabling clearer roadmap execution. Priority 1 validator alignment will reduce future ambiguity in error messaging across all subsystems.

- AI-assisted feature work can now reference these docs with confidence that terminology and contract are aligned.

