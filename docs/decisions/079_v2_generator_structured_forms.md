# Context
- `schema_project_v2` inherited the classic/kit column editor where most generator configuration depended on raw JSON entry.
- We needed to move the majority of generator setup into GUI controls without breaking deterministic behavior, JSON compatibility, or classic-route rollback safety.

# Decision
- Added a v2-only structured generator form contract at `src/gui_v2/generator_forms.py`:
  - `GeneratorFieldSpec`
  - `GeneratorFormSpec`
  - `GeneratorFormState`
- Implemented dynamic structured generator fields in `src/gui_v2_schema_project.py` for all registered generators.
- Kept raw `Generator params JSON` entry/editor as an advanced fallback path.
- Added two-way sync between structured fields and raw params JSON.
- Added passthrough preservation of unknown params keys so JSON roundtrips do not lose non-form keys.
- Added source-column dependency auto-add behavior for generator fields that require `depends_on` linkage (`if_then`, `time_offset`, `sample_csv`, `hierarchical_category` source selectors).
- Added advanced optional controls for `null_rate`, `outlier_rate`, `outlier_scale`, and bytes length bounds.

# Consequences
- v2 schema authoring now supports structured generator setup for mainstream and advanced paths without forcing manual JSON for common cases.
- Classic schema routes remain unchanged and continue to serve as rollback-safe behavior baselines.
- Validator/runtime contracts remain authoritative and unchanged; this is a v2 UI-layer enhancement only.
- Unknown generator params keys are preserved instead of being dropped during structured edits.

# Test impact
- Added `tests/test_gui_v2_generator_forms.py` for generator form coverage/parsing/split-state contracts.
- Added `tests/test_gui_v2_schema_project_generator_ui.py` for v2 structured-sync behavior, unknown-key preservation, dependency auto-add, v2-only isolation, and save/load roundtrip checks.
- Confirmed v2 parity route baseline remains intact via `tests/test_gui_schema_project_v2_parity.py`.
