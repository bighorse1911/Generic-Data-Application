from __future__ import annotations

import importlib
import unittest


class ImportContractTests(unittest.TestCase):
    def test_legacy_schema_import_surface(self) -> None:
        mod = importlib.import_module("src.schema_project_model")
        for name in (
            "ColumnSpec",
            "TableSpec",
            "ForeignKeySpec",
            "SchemaProject",
            "SUPPORTED_DTYPES",
            "validate_project",
            "correlation_cholesky_lower",
        ):
            self.assertTrue(hasattr(mod, name), f"Missing legacy schema symbol: {name}")

    def test_legacy_generation_import_surface(self) -> None:
        mod = importlib.import_module("src.generator_project")
        for name in (
            "generate_project_rows",
            "generate_project_rows_streaming",
            "_dependency_order",
            "dependency_order",
        ):
            self.assertTrue(hasattr(mod, name), f"Missing legacy generation symbol: {name}")

    def test_derived_expression_import_surface(self) -> None:
        mod = importlib.import_module("src.derived_expression")
        for name in (
            "CompiledDerivedExpression",
            "compile_derived_expression",
            "evaluate_derived_expression",
            "extract_derived_expression_references",
            "is_iso_date_text",
            "is_iso_datetime_text",
            "MAX_EXPRESSION_LENGTH",
            "MAX_EXPRESSION_NODES",
            "MAX_EXPRESSION_DEPTH",
            "_ExpressionValidator",
            "_ExpressionEvaluator",
            "_expression_error",
            "_is_scalar_literal",
            "_is_number",
        ):
            self.assertTrue(hasattr(mod, name), f"Missing derived_expression symbol: {name}")

    def test_legacy_generator_registry_surface(self) -> None:
        mod = importlib.import_module("src.generators")
        for name in ("GenContext", "register", "get_generator", "reset_runtime_generator_state"):
            self.assertTrue(hasattr(mod, name), f"Missing legacy generator symbol: {name}")

    def test_generation_generator_registry_surface(self) -> None:
        mod = importlib.import_module("src.generation.generator_registry")
        for name in (
            "GenContext",
            "REGISTRY",
            "register",
            "get_generator",
            "reset_runtime_generator_state",
            "gen_latitude",
            "gen_longitude",
            "gen_money",
            "gen_percent",
            "gen_date",
            "gen_timestamp_utc",
            "gen_sample_csv",
            "gen_if_then",
            "gen_hierarchical_category",
            "gen_time_offset",
            "gen_normal",
            "gen_uniform_int",
            "gen_uniform_float",
            "gen_lognormal",
            "gen_choice_weighted",
            "gen_ordered_choice",
            "gen_state_transition",
            "gen_derived_expr",
            "gen_salary_from_age",
        ):
            self.assertTrue(hasattr(mod, name), f"Missing generation registry symbol: {name}")

    def test_legacy_gui_import_surface(self) -> None:
        schema_mod = importlib.import_module("src.gui_schema_core")
        for name in (
            "SchemaProjectDesignerScreen",
            "ValidationHeatmap",
            "ValidationIssue",
            "ScrollableFrame",
            "filedialog",
            "messagebox",
            "save_project_to_json",
            "load_project_from_json",
        ):
            self.assertTrue(hasattr(schema_mod, name), f"Missing legacy gui schema symbol: {name}")

        redesign_mod = importlib.import_module("src.gui_v2_redesign")
        for name in (
            "V2ShellFrame",
            "HomeV2Screen",
            "SchemaStudioV2Screen",
            "RunCenterV2Screen",
            "ERDDesignerV2Screen",
            "LocationSelectorV2Screen",
            "GenerationBehaviorsGuideV2Screen",
            "run_shared_estimate",
            "run_shared_build_partition_plan",
            "run_shared_benchmark",
            "build_profile_from_model",
            "run_generation_multiprocess",
            "filedialog",
        ):
            self.assertTrue(hasattr(redesign_mod, name), f"Missing legacy gui v2 symbol: {name}")

        erd_view_mod = importlib.import_module("src.gui_tools.erd_designer_view")
        self.assertTrue(
            hasattr(erd_view_mod, "ERDDesignerToolFrame"),
            "Missing gui tool symbol: ERDDesignerToolFrame",
        )
        gui_tools_mod = importlib.import_module("src.gui_tools")
        self.assertTrue(
            hasattr(gui_tools_mod, "ERDDesignerToolFrame"),
            "Missing gui_tools export: ERDDesignerToolFrame",
        )

    def test_erd_designer_import_surface(self) -> None:
        mod = importlib.import_module("src.erd_designer")
        for name in (
            "ERD_AUTHORING_DTYPES",
            "new_erd_schema_project",
            "add_table_to_erd_project",
            "add_column_to_erd_project",
            "add_relationship_to_erd_project",
            "update_table_in_erd_project",
            "update_column_in_erd_project",
            "export_schema_project_to_json",
            "load_project_schema_for_erd",
            "ERDNode",
            "ERDEdge",
            "build_table_detail_lines",
            "build_erd_layout",
            "edge_label",
            "node_anchor_y",
            "table_for_edge",
            "relation_lines",
            "apply_node_position_overrides",
            "compute_diagram_size",
            "build_erd_svg",
            "export_erd_file",
            "_find_ghostscript_executable",
            "_export_raster_with_ghostscript",
        ):
            self.assertTrue(hasattr(mod, name), f"Missing erd_designer symbol: {name}")

    def test_new_domain_paths_import(self) -> None:
        modules = (
            "src.schema",
            "src.schema.types",
            "src.schema.validate",
            "src.generation",
            "src.generation.pipeline",
            "src.generation.dependency",
            "src.generation.generator_registry",
            "src.generation.quality_profiles_helpers",
            "src.generation.quality_profiles_compile",
            "src.generation.quality_profiles_apply",
            "src.runtime.performance",
            "src.runtime.multiprocessing",
            "src.gui_v2_schema_project_layout",
            "src.gui_v2_schema_project_form",
            "src.gui.schema.classic_screen",
            "src.gui.schema.classic.layout_init",
            "src.gui.schema.classic.layout_build",
            "src.gui.schema.classic.layout_table_selection",
            "src.gui.schema.classic.layout_navigation",
            "src.gui.schema.classic.actions_columns_editor",
            "src.gui.schema.classic.actions_columns_spec",
            "src.gui.schema.classic.actions_columns_mutations",
            "src.gui.schema.editor_base",
            "src.gui.schema.editor.base_types",
            "src.gui.schema.editor.context_binding",
            "src.gui.schema.editor.layout_panels_project",
            "src.gui.schema.editor.layout_panels_tables",
            "src.gui.schema.editor.layout_panels_columns",
            "src.gui.schema.editor.layout_panels_relationships",
            "src.gui.schema.editor.layout_panels_generate",
            "src.gui.erd.layout",
            "src.gui.erd.authoring_tables",
            "src.gui.erd.authoring_columns",
            "src.gui.erd.authoring_relationships",
            "src.gui.erd.authoring_rename_refs",
            "src.gui_tools.erd_designer",
            "src.gui_tools.erd_designer.build",
            "src.gui_tools.erd_designer.helpers",
            "src.gui_tools.erd_designer.authoring_sync",
            "src.gui_tools.erd_designer.authoring_actions",
            "src.gui_tools.erd_designer.io_export",
            "src.gui_tools.erd_designer.rendering",
            "src.gui_tools.erd_designer.dragging",
            "src.gui.v2.routes.home",
            "src.gui.v2.routes.schema_studio",
            "src.gui.v2.routes.run_center",
        )
        for module_name in modules:
            mod = importlib.import_module(module_name)
            self.assertIsNotNone(mod, f"Failed to import {module_name}")

    def test_runtime_import_surfaces(self) -> None:
        perf_required = (
            "OUTPUT_MODES",
            "FK_CACHE_MODES",
            "PerformanceProfile",
            "WorkloadEstimate",
            "WorkloadSummary",
            "ChunkPlanEntry",
            "ChunkPlanSummary",
            "RuntimeEvent",
            "BenchmarkResult",
            "StrategyRunResult",
            "PerformanceRunCancelled",
            "build_performance_profile",
            "validate_performance_profile",
            "build_chunk_plan",
            "estimate_workload",
            "summarize_estimates",
            "summarize_chunk_plan",
            "run_performance_benchmark",
            "run_generation_with_strategy",
        )
        mp_required = (
            "EXECUTION_MODES",
            "MultiprocessConfig",
            "PartitionPlanEntry",
            "WorkerStatus",
            "PartitionFailure",
            "MultiprocessEvent",
            "MultiprocessRunResult",
            "MultiprocessRunCancelled",
            "build_multiprocess_config",
            "validate_multiprocess_config",
            "multiprocess_config_to_payload",
            "multiprocess_config_from_payload",
            "build_partition_plan",
            "build_worker_status_snapshot",
            "derive_partition_seed",
            "create_run_ledger",
            "save_run_ledger",
            "load_run_ledger",
            "validate_run_ledger",
            "apply_run_ledger_to_plan",
            "run_generation_with_multiprocessing",
        )

        perf_modules = (
            importlib.import_module("src.performance_scaling"),
            importlib.import_module("src.runtime.performance"),
        )
        for mod in perf_modules:
            for name in perf_required:
                self.assertTrue(hasattr(mod, name), f"Missing runtime performance symbol: {name}")

        mp_modules = (
            importlib.import_module("src.multiprocessing_runtime"),
            importlib.import_module("src.runtime.multiprocessing"),
        )
        for mod in mp_modules:
            for name in mp_required:
                self.assertTrue(hasattr(mod, name), f"Missing runtime multiprocessing symbol: {name}")


if __name__ == "__main__":
    unittest.main()
