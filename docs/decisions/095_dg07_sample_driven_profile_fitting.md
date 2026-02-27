# 095 - DG07 Sample-Driven Profile Fitting

## Context
- `NEXT_DECISIONS.md` prioritized DG07 to bootstrap generator profiles from sample CSV data while preserving deterministic generation.
- Existing behavior required manual generator parameter authoring; there was no project-level profile-fit inference contract.
- DG07 required additive behavior, actionable validation/runtime errors, JSON roundtrip support, and GUI project-level authoring exposure.

## Decision
- Extended project contract in `src/schema_project_model.py`:
  - added optional `SchemaProject.sample_profile_fits`.
  - validated fit shape/semantics for unique `fit_id`, target table/column existence, non-PK targets, one fit per target, `strategy='auto'`, and `sample_source` / `fixed_profile` contracts.
  - enforced DG07 guardrails for unsupported inference targets (`bool`, `bytes`) and actionable error messages.
- Implemented deterministic DG07 runtime profile resolution in `src/generator_project.py`:
  - added CSV sample-source reader with header/index/name resolution and eligibility filtering.
  - added dtype-aware profile inference mapping (`uniform_int`, `normal`/`uniform_float`, `choice_weighted`, `date`, `timestamp_utc`).
  - added fit-override resolution pass that creates an effective project before generation and re-validates the effective schema.
- Updated JSON IO in `src/schema_project_io.py`:
  - load/save now preserve `sample_profile_fits`.
  - CSV paths under `sample_profile_fits[*].sample_source.path` are normalized to repo-relative form when possible, consistent with existing sample CSV portability behavior.
- Added GUI authoring exposure:
  - `src/gui_schema_core.py` project panel now includes `Sample profile fits JSON (optional)` with JSON editor + parse/validation bridge.
  - `src/gui_schema_editor_base.py` carries the same project-level control through native v2 layout, load/apply, and incremental validation projection paths.
  - `src/gui_tools/generation_guide_view.py` includes a DG07 guide entry.
- Preserved DG07 field through project-copy workflows:
  - `src/erd_designer.py`,
  - `src/performance_scaling.py`,
  - runtime effective-project construction.
- Added/updated regression coverage:
  - `tests/test_sample_profile_fitting.py` for DG07 inference/fixed-profile determinism and validation.
  - `tests/test_schema_project_roundtrip.py` for DG07 roundtrip and path normalization.
  - `tests/test_gui_v2_schema_project_generator_ui.py` for v2 project-level sample-profile-fits save/load roundtrip.
  - `tests/test_invariants.py` for DG07 guide entry assertions.

## Consequences
- DG07 is opt-in and backward compatible: existing schemas remain valid without `sample_profile_fits`.
- Teams can bootstrap generator behavior from representative CSV samples without introducing non-deterministic runtime behavior.
- Fixed profile mode provides a stable freeze point for inferred profiles in regulated/repeatable test scenarios.
- Invalid fit configs fail fast with actionable hints before generation.
