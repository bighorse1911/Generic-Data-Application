# 090 - DG02 State Transition Generator

## Context
- `NEXT_DECISIONS.md` prioritized DG02 to improve lifecycle realism with deterministic per-entity state trajectories.
- Existing generators supported conditional logic and ordered progression, but did not provide explicit transition-graph + dwell semantics.
- DG02 required additive rollout with validator/runtime/GUI/doc/test parity and no external dependencies.

## Decision
- Added new generator `state_transition` with:
  - required `entity_column`, `states`, and `transitions`,
  - optional `start_state` or `start_weights` (mutually exclusive),
  - optional `terminal_states`,
  - optional global dwell controls (`dwell_min`, `dwell_max`) and per-state overrides (`dwell_by_state`).
- Implemented runtime generator behavior in `src/generators.py`:
  - deterministic per-entity trajectory state cache keyed by table/column/entity identity,
  - allowed-transition weighted progression,
  - explicit terminal-state absorption,
  - strict dwell-run handling before transitions.
- Added validator guardrails in `src/schema_project_model.py`:
  - dtype restriction to `text|int`,
  - `entity_column` existence/self/`depends_on` checks,
  - state list typing/uniqueness checks,
  - start config mutual exclusion checks,
  - transition-map, terminal-state, self-edge, and dwell bounds checks.
- Extended SCD2 tracked-column mutation in `src/generator_project.py`:
  - `state_transition` tracked columns now advance by one valid transition step per SCD2 version increment,
  - terminal states remain absorbing,
  - dwell is intentionally ignored in SCD2 mutation path.
- Added GUI authoring exposure:
  - classic generator catalog/filter/template updates in `src/gui_schema_core.py`,
  - v2 structured generator form spec in `src/gui_v2/generator_forms.py`,
  - generation guide card in `src/gui_tools/generation_guide_view.py`.
- Updated canonical docs and roadmap files:
  - `DATA_SEMANTICS.md`,
  - `PROJECT_CANON.md`,
  - `GUI_WIREFRAME_SCHEMA.md`,
  - `NEXT_DECISIONS.md`.

## Consequences
- Users can model deterministic lifecycle/status trajectories with explicit transition constraints and dwell behavior.
- Invalid DG02 configs fail fast with canonical actionable error messages.
- SCD2 tracked columns using `state_transition` now preserve transition semantics rather than falling back to generic mutation behavior.
- Coverage expanded via:
  - new `tests/test_state_transition_generator.py`,
  - SCD2 regression in `tests/test_scd_generation.py`,
  - GUI/invariant updates in `tests/test_gui_generator_filtering.py`, `tests/test_gui_v2_generator_forms.py`, and `tests/test_invariants.py`.
