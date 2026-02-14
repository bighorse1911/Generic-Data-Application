# Context
- Prompt requested a review of all items currently listed under **In Progress** and to remove anything already completed, marking those items as complete.
- Canon/roadmap status had drifted after recent Priority 1 feature delivery work.

# Decision
- Updated roadmap status tracking so completed items were moved out of **In Progress**:
  - moved CSV column sampling to completed,
  - moved Priority 1 phased rollout (phases 1-5) to completed,
  - moved DATA_SEMANTICS/GUI_WIREFRAME canonical adoption items to completed.
- Kept only unfinished items in **In Progress**:
  - extensible data types,
  - realistic distributions.
- Added small status-sync lines in canon/spec docs confirming Priority 1 rollout completion.

# Consequences
- `NEXT_DECISIONS.md` now reflects actual implementation status and no longer tracks completed work as active.
- Current in-progress queue is narrower and clearer for future planning/execution.
