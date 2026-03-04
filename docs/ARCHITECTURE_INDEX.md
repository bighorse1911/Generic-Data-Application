# Architecture Index

This file is the navigation map for the domain-first incremental refactor.

## Entrypoints

- GUI app entrypoint: `src/main.py`
- App shell + route registry: `src/gui_home.py`
- Canonical route constants: `src/gui_route_policy.py`

## Domain Packages

### Schema Domain

- Public package: `src/schema/`
- Compatibility model hub: `src/schema/model_impl.py` (dataclasses + compatibility wrappers)
- Public API modules:
  - `src/schema/types.py`
  - `src/schema/validate.py`
  - `src/schema/validation_errors.py`
- Validator ownership modules:
  - `src/schema/validators/generators.py` (strict-order validation orchestrator + compatibility surface)
  - `src/schema/validators/project_table_rules.py` (project/table/column structural checks)
  - `src/schema/validators/generator_param_parsing.py` (generator parameter parse helpers)
  - `src/schema/validators/generator_rules_numeric.py` (numeric/categorical generator checks)
  - `src/schema/validators/generator_rules_dependency.py` (depends_on and derived/sample/time-offset/hierarchical checks)
  - `src/schema/validators/state_transition.py` (state-transition generator validation)
  - `src/schema/validators/correlation.py` (correlation matrix + group checks)
  - `src/schema/validators/scd.py` (business-key/SCD checks)
  - `src/schema/validators/fk.py` (FK + parent-selection + child-cardinality profiles)
  - `src/schema/validators/timeline.py` (DG03 timeline constraints)
  - `src/schema/validators/quality_profile_fit.py` (DG06/DG07 compatibility surface)
  - `src/schema/validators/dg06_quality_profiles.py` (DG06 quality profile validation)
  - `src/schema/validators/dg07_sample_profile_fit.py` (DG07 sample-profile fit validation)
  - `src/schema/validators/locale.py` (DG09 locale identity bundles)
  - `src/schema/validators/common.py` (shared validator parse/error helpers)
- Compatibility shim: `src/schema_project_model.py`

### Generation Domain

- Public package: `src/generation/`
- Facade/public entrypoints: `src/generation/pipeline.py`
- Internal orchestration: `src/generation/pipeline_orchestrator.py`
- Shared helpers: `src/generation/common.py`
- Registry foundations:
  - `src/generation/registry_core.py` (`GenContext`, `REGISTRY`, `register`, `get_generator`)
  - `src/generation/generator_state.py` (runtime cache state + reset lifecycle)
  - `src/generation/generator_common.py` (shared generator error/parse helpers)
- Concern ownership modules:
  - `src/generation/dependency.py` (`_dependency_order`, `dependency_order`)
  - `src/generation/fk_assignment.py` (FK parent weighting and child-count allocation)
  - `src/generation/timeline.py` (DG03 compile/enforce helpers)
  - `src/generation/quality_profiles.py` (DG06 thin compatibility facade)
  - `src/generation/quality_profiles_helpers.py` (DG06 scalar/probability/where + format-error helpers)
  - `src/generation/quality_profiles_compile.py` (DG06 profile compile/validation)
  - `src/generation/quality_profiles_apply.py` (DG06 row-level mutation application)
  - `src/generation/locale_identity.py` (DG09 compile/apply helpers)
  - `src/generation/profile_fit.py` (DG07 sample-source/profile-fit helpers)
  - `src/generation/correlation.py` (DG01 correlation helpers)
  - `src/generation/scd.py` (business-key/SCD helpers)
  - `src/generation/value_generation.py` (column-value generation and dependency ordering)
- Builtin generator owners:
  - `src/generation/builtins/numeric.py`
  - `src/generation/builtins/temporal.py`
  - `src/generation/builtins/categorical.py`
  - `src/generation/builtins/conditional.py`
  - `src/generation/builtins/lifecycle.py`
  - `src/generation/builtins/derived_expr.py`
- Generator registry compatibility facade + bootstrap loader: `src/generation/generator_registry.py`
- Compatibility shims:
  - `src/generator_project.py`
  - `src/generators.py`

### Runtime Domain

- Public package: `src/runtime/`
- Runtime concern ownership modules:
  - `src/runtime/core/perf_types.py` (performance constants + dataclasses)
  - `src/runtime/core/perf_profile.py` (performance profile parsing/build)
  - `src/runtime/core/perf_planning.py` (profile validation + chunk planning)
  - `src/runtime/core/perf_estimation.py` (workload estimate + summary)
  - `src/runtime/core/perf_execution.py` (benchmark + strategy execution)
  - `src/runtime/core/mp_types.py` (multiprocess constants + dataclasses)
  - `src/runtime/core/mp_config.py` (multiprocess config parsing/validation/payload)
  - `src/runtime/core/mp_partition.py` (partition planning + worker snapshot)
  - `src/runtime/core/mp_ledger.py` (run-ledger create/load/save/validate/apply)
  - `src/runtime/core/mp_execution.py` (multiprocess orchestration + fallback)
- Top-level canonical facades:
  - `src/performance_scaling.py`
  - `src/multiprocessing_runtime.py`
- Compatibility wrappers:
  - `src/runtime/performance.py` -> `src/performance_scaling.py`
  - `src/runtime/multiprocessing.py` -> `src/multiprocessing_runtime.py`

### Expression Engine

- Compatibility facade:
  - `src/derived_expression.py` (thin compatibility facade and stable import surface)
- Concern ownership modules:
  - `src/derived_expression_common.py` (shared error/scalar helpers)
  - `src/derived_expression_types.py` (limits + compiled-expression dataclass)
  - `src/derived_expression_validator.py` (AST validation + reference extraction)
  - `src/derived_expression_evaluator.py` (runtime expression evaluation + DSL functions)
  - `src/derived_expression_compile.py` (compile and reference-extract API functions)
  - `src/derived_expression_datetime.py` (ISO date/datetime text helpers)

### GUI Domain

- Public package: `src/gui/`
- ERD implementation ownership:
  - `src/gui/erd/common.py` (error contracts + authoring parse helpers + dtype policy)
  - `src/gui/erd/authoring.py` (thin compatibility facade for ERD authoring mutations)
  - `src/gui/erd/authoring_tables.py` (schema creation + table add/edit mutation flows)
  - `src/gui/erd/authoring_columns.py` (column add/edit mutation flows + FK-aware rename propagation)
  - `src/gui/erd/authoring_relationships.py` (relationship add validation/mutation flow)
  - `src/gui/erd/authoring_rename_refs.py` (shared column-rename replacement helpers)
  - `src/gui/erd/project_io.py` (schema load/export JSON helpers)
  - `src/gui/erd/layout.py` (ERD node/edge models + layout computation helpers)
  - `src/gui/erd/svg.py` (SVG rendering helpers)
  - `src/gui/erd/raster.py` (Ghostscript/raster export helpers)
  - `src/erd_designer.py` (thin compatibility facade and legacy patch bridge for `_find_ghostscript_executable`)
- ERD tool-frame UI ownership:
  - `src/gui_tools/erd_designer/build.py` (frame construction + section layout wiring)
  - `src/gui_tools/erd_designer/helpers.py` (error/combo/table-lookup helpers)
  - `src/gui_tools/erd_designer/authoring_sync.py` (editor sync/reset/shared-save handlers)
  - `src/gui_tools/erd_designer/authoring_actions.py` (create/add/edit authoring mutations)
  - `src/gui_tools/erd_designer/io_export.py` (load/render/export actions)
  - `src/gui_tools/erd_designer/rendering.py` (canvas render pipeline + option toggles)
  - `src/gui_tools/erd_designer/dragging.py` (table drag hit-testing and motion handlers)
  - `src/gui_tools/erd_designer_view.py` (thin compatibility facade exposing `ERDDesignerToolFrame`)
- Schema GUI implementation:
  - `src/gui_v2_schema_project.py` (thin compatibility facade for schema v2 route class)
  - `src/gui_v2_schema_project_layout.py` (schema v2 header/back/layout panel attachment helpers)
  - `src/gui_v2_schema_project_form.py` (schema v2 structured generator-form build/sync/validation helpers)
  - `src/gui/schema/classic_screen.py`
  - `src/gui/schema/classic/constants.py`
  - `src/gui/schema/classic/widgets.py`
  - `src/gui/schema/classic/layout.py` (thin compatibility hub / delegated exports)
  - `src/gui/schema/classic/layout_init.py` (screen init state/vars/traces startup sequence)
  - `src/gui/schema/classic/layout_build.py` (UI section construction for classic schema screen)
  - `src/gui/schema/classic/layout_table_selection.py` (table/editor enablement and selection load flows)
  - `src/gui/schema/classic/layout_navigation.py` (back navigation and DB path browse helpers)
  - `src/gui/schema/classic/state_dirty.py`
  - `src/gui/schema/classic/validation.py`
  - `src/gui/schema/classic/preview.py`
  - `src/gui/schema/classic/project_io.py`
  - `src/gui/schema/classic/actions_tables.py`
  - `src/gui/schema/classic/actions_columns.py` (thin compatibility hub / delegated exports)
  - `src/gui/schema/classic/actions_columns_editor.py` (column editor UI sync/filter/preset/template helpers)
  - `src/gui/schema/classic/actions_columns_spec.py` (column spec parsing/validation helpers)
  - `src/gui/schema/classic/actions_columns_mutations.py` (column add/edit/remove/reorder mutation flows)
  - `src/gui/schema/classic/actions_fks.py`
  - `src/gui/schema/classic/actions_generation.py`
  - `src/gui/schema/editor_base.py`
  - `src/gui/schema/constants.py`
  - `src/gui/schema/widgets.py`
  - `src/gui/schema/editor/base_types.py` (shared editor constants + lightweight dataclass types)
  - `src/gui/schema/editor/context_binding.py` (module-context binding helper + bound-module registry)
  - `src/gui/schema/editor/jobs.py` (threaded job dispatch and run/project-io lifecycle guards)
  - `src/gui/schema/editor/layout.py` (thin compatibility hub / delegated exports)
  - `src/gui/schema/editor/layout_build.py` (`_build`, route show/hide hooks, header/status-bar wiring)
  - `src/gui/schema/editor/layout_modes.py` (schema-design-mode state + visibility/preservation policy)
  - `src/gui/schema/editor/layout_panels.py` (thin compatibility hub / delegated exports)
  - `src/gui/schema/editor/layout_panels_project.py` (project panel ownership)
  - `src/gui/schema/editor/layout_panels_tables.py` (tables panel ownership)
  - `src/gui/schema/editor/layout_panels_columns.py` (columns panel ownership)
  - `src/gui/schema/editor/layout_panels_relationships.py` (relationships panel ownership)
  - `src/gui/schema/editor/layout_panels_generate.py` (generate/preview/export panel ownership)
  - `src/gui/schema/editor/layout_navigation.py` (back-tab-destroy route lifecycle hooks)
  - `src/gui/schema/editor/layout_shortcuts.py` (shortcut registration + focus-anchor registry)
  - `src/gui/schema/editor/layout_onboarding.py` (first-run/empty-state hint lifecycle)
  - `src/gui/schema/editor/validation.py` (full/incremental validation orchestration and summaries)
  - `src/gui/schema/editor/filters.py` (search index/paging/filter-tree rendering helpers)
  - `src/gui/schema/editor/preview.py` (preview projection, paging, and column chooser flow)
  - `src/gui/schema/editor/project_io.py` (save/load async flows + starter fixture shortcuts)
  - `src/gui/schema/editor/actions_tables.py` (table add/remove/edit action handlers)
  - `src/gui/schema/editor/actions_columns.py` (column add/remove/edit/reorder action handlers)
  - `src/gui/schema/editor/actions_fks.py` (relationship add/remove action handlers)
  - `src/gui/schema/editor/actions_generation.py` (generate/export/sqlite/sample handlers)
  - `src/gui/schema/editor/state_undo.py` (undo/redo + workspace-state persistence helpers)
- V2 route implementation split:
  - `src/gui/v2/routes/theme_shared.py`
  - `src/gui/v2/routes/adapters.py`
  - `src/gui/v2/routes/errors.py`
  - `src/gui/v2/routes/shell_impl.py`
  - `src/gui/v2/routes/home_impl.py`
  - `src/gui/v2/routes/schema_studio_impl.py`
  - `src/gui/v2/routes/run_center_nav.py`
  - `src/gui/v2/routes/run_center_io.py`
  - `src/gui/v2/routes/run_center_runs.py`
  - `src/gui/v2/routes/run_center_impl.py`
  - `src/gui/v2/routes/specialists_impl.py`
  - `src/gui/v2/routes/run_hooks.py`
  - `src/gui/v2/routes/_route_impl.py` (thin compatibility hub only)
  - `src/gui/v2/routes/home.py`
  - `src/gui/v2/routes/schema_studio.py`
  - `src/gui/v2/routes/run_center.py`
  - `src/gui/v2/routes/erd_designer.py`
  - `src/gui/v2/routes/location_selector.py`
  - `src/gui/v2/routes/generation_guide.py`
  - `src/gui/v2/routes/shell.py`
- Compatibility shims:
  - `src/gui_schema_core.py`
  - `src/gui_schema_editor_base.py`
  - `src/gui_v2_redesign.py` (must preserve legacy module-level patch points such as `run_shared_estimate`, `run_shared_build_partition_plan`, `run_shared_benchmark`, `build_profile_from_model`, `run_generation_multiprocess`, and `filedialog`; these bridge into `src/gui/v2/routes/run_hooks.py`)

## Where To Edit

| Goal | Primary file(s) |
|---|---|
| Add/adjust schema dataclasses | `src/schema/types.py` + `src/schema/model_impl.py` |
| Change schema validation behavior | `src/schema/validate.py` + `src/schema/validators/*.py` |
| Change row generation flow | `src/generation/pipeline_orchestrator.py` + concern modules in `src/generation/*.py` |
| Change FK ordering for generation/storage | `src/generation/dependency.py` |
| Add/adjust generators | builtin owner modules in `src/generation/builtins/*.py` + registry foundations in `src/generation/registry_core.py`; compatibility path remains `src/generation/generator_registry.py` |
| Update performance strategy runtime | `src/runtime/core/perf_*.py` + facade `src/performance_scaling.py` |
| Update multiprocess orchestration runtime | `src/runtime/core/mp_*.py` + facade `src/multiprocessing_runtime.py` |
| Update ERD authoring/layout/export behavior | `src/gui/erd/*.py` with compatibility path `src/erd_designer.py` |
| Update ERD tool-frame UI behavior | `src/gui_tools/erd_designer/*.py` with compatibility path `src/gui_tools/erd_designer_view.py` |
| Update classic schema GUI behavior | `src/gui/schema/classic/*.py` and thin hub `src/gui/schema/classic_screen.py` |
| Update schema v2 route generator-form behavior | `src/gui_v2_schema_project_form.py` with class facade `src/gui_v2_schema_project.py` |
| Update schema-editor concern logic | `src/gui/schema/editor/*.py` (layout split ownership in `layout_build.py`, `layout_modes.py`, `layout_panels_{project,tables,columns,relationships,generate}.py`, `layout_navigation.py`, `layout_shortcuts.py`, `layout_onboarding.py`; wrappers remain in `src/gui/schema/editor_base.py`) |
| Update v2 navigation shell routes | `src/gui/v2/routes/*_impl.py` + route wrappers in `src/gui/v2/routes/*.py` |
| Update run-center v2 route behavior | `src/gui/v2/routes/run_center_nav.py`, `src/gui/v2/routes/run_center_io.py`, `src/gui/v2/routes/run_center_runs.py` with wrapper surface in `src/gui/v2/routes/run_center_impl.py` |
| Update run-center patchable command hooks | `src/gui/v2/routes/run_hooks.py` and compatibility bridge `src/gui_v2_redesign.py` |
| Keep backward import compatibility | top-level shim modules in `src/` |

## Test Organization

Tests are organized by subsystem under `tests/`:

- `tests/schema/`
- `tests/generation/`
- `tests/runtime/`
- `tests/gui/`
- `tests/integration/`

Compatibility and guardrail tests remain at the root of `tests/`:

- `tests/test_import_contracts.py`
- `tests/test_module_size_budget.py`
- `run_gui_tests_isolated.py` runs GUI modules in isolated subprocesses with per-module timeout to reduce Tk lifecycle bleed across modules.

## Compatibility Policy

- Existing imports from top-level modules remain supported via shims.
- New domain-first imports are preferred for future changes.
- Shim removal is deferred until all callers migrate and a stable release cycle passes.
