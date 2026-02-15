from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.gui_kit import run_commands as shared_run_commands
from src.gui_v2.viewmodels import RunCenterViewModel
from src.multiprocessing_runtime import MultiprocessConfig
from src.multiprocessing_runtime import MultiprocessEvent
from src.multiprocessing_runtime import MultiprocessRunResult
from src.multiprocessing_runtime import PartitionPlanEntry
from src.performance_scaling import BenchmarkResult
from src.performance_scaling import PerformanceProfile
from src.performance_scaling import RuntimeEvent
from src.performance_scaling import WorkloadEstimate
from src.performance_scaling import WorkloadSummary
from src.location_selector import build_circle_geojson
from src.location_selector import sample_points_within_radius
from src.location_selector import write_points_csv
from src.erd_designer import add_column_to_erd_project
from src.erd_designer import add_relationship_to_erd_project
from src.erd_designer import add_table_to_erd_project
from src.erd_designer import build_erd_svg
from src.erd_designer import export_erd_file
from src.erd_designer import export_schema_project_to_json
from src.erd_designer import load_project_schema_for_erd
from src.erd_designer import new_erd_schema_project
from src.erd_designer import update_column_in_erd_project
from src.erd_designer import update_table_in_erd_project
from src.schema_project_model import SchemaProject
from src.schema_project_model import SchemaProject as SchemaProjectType


@dataclass(frozen=True)
class RunCenterDiagnostics:
    estimates: list[WorkloadEstimate]
    summary: WorkloadSummary


def location_build_geojson(center_lat: object, center_lon: object, radius_km: object, *, steps: object) -> dict[str, object]:
    return build_circle_geojson(center_lat, center_lon, radius_km, steps=steps)


def location_generate_points(
    center_lat: object,
    center_lon: object,
    radius_km: object,
    *,
    count: object,
    seed: object,
) -> list[tuple[float, float]]:
    return sample_points_within_radius(
        center_lat,
        center_lon,
        radius_km,
        count=count,
        seed=seed,
    )


def location_save_points_csv(path: object, points: list[tuple[float, float]]):
    return write_points_csv(path, points)


def erd_new_project(*, name_value: object, seed_value: object = 12345) -> SchemaProjectType:
    return new_erd_schema_project(name_value=name_value, seed_value=seed_value)


def erd_add_table(project: object, *, table_name_value: object, row_count_value: object = 100) -> SchemaProjectType:
    return add_table_to_erd_project(
        project,
        table_name_value=table_name_value,
        row_count_value=row_count_value,
    )


def erd_add_column(
    project: object,
    *,
    table_name_value: object,
    column_name_value: object,
    dtype_value: object,
    primary_key: bool = False,
    nullable: bool = True,
) -> SchemaProjectType:
    return add_column_to_erd_project(
        project,
        table_name_value=table_name_value,
        column_name_value=column_name_value,
        dtype_value=dtype_value,
        primary_key=primary_key,
        nullable=nullable,
    )


def erd_add_relationship(
    project: object,
    *,
    child_table_value: object,
    child_column_value: object,
    parent_table_value: object,
    parent_column_value: object,
    min_children_value: object = 1,
    max_children_value: object = 3,
) -> SchemaProjectType:
    return add_relationship_to_erd_project(
        project,
        child_table_value=child_table_value,
        child_column_value=child_column_value,
        parent_table_value=parent_table_value,
        parent_column_value=parent_column_value,
        min_children_value=min_children_value,
        max_children_value=max_children_value,
    )


def erd_update_table(
    project: object,
    *,
    current_table_name_value: object,
    new_table_name_value: object,
    row_count_value: object,
) -> SchemaProjectType:
    return update_table_in_erd_project(
        project,
        current_table_name_value=current_table_name_value,
        new_table_name_value=new_table_name_value,
        row_count_value=row_count_value,
    )


def erd_update_column(
    project: object,
    *,
    table_name_value: object,
    current_column_name_value: object,
    new_column_name_value: object,
    dtype_value: object,
    primary_key: bool,
    nullable: bool,
) -> SchemaProjectType:
    return update_column_in_erd_project(
        project,
        table_name_value=table_name_value,
        current_column_name_value=current_column_name_value,
        new_column_name_value=new_column_name_value,
        dtype_value=dtype_value,
        primary_key=primary_key,
        nullable=nullable,
    )


def erd_load_project(path_value: object) -> SchemaProjectType:
    return load_project_schema_for_erd(path_value)


def erd_export_schema_json(*, project: object, output_path_value: object):
    return export_schema_project_to_json(project=project, output_path_value=output_path_value)


def erd_build_svg(
    project: SchemaProjectType,
    *,
    show_relationships: bool,
    show_columns: bool,
    show_dtypes: bool,
    node_positions: dict[str, tuple[int, int]] | None = None,
) -> str:
    return build_erd_svg(
        project,
        show_relationships=show_relationships,
        show_columns=show_columns,
        show_dtypes=show_dtypes,
        node_positions=node_positions,
    )


def erd_export_file(
    *,
    output_path_value: object,
    svg_text: str,
    postscript_data: str | None = None,
):
    return export_erd_file(
        output_path_value=output_path_value,
        svg_text=svg_text,
        postscript_data=postscript_data,
    )


def build_profile_from_viewmodel(viewmodel: RunCenterViewModel) -> PerformanceProfile:
    return shared_run_commands.build_profile_from_model(viewmodel)


def build_config_from_viewmodel(viewmodel: RunCenterViewModel) -> MultiprocessConfig:
    return shared_run_commands.build_config_from_model(viewmodel)


def run_estimate(project: SchemaProject, viewmodel: RunCenterViewModel) -> RunCenterDiagnostics:
    diagnostics = shared_run_commands.run_estimate(project, viewmodel)
    return RunCenterDiagnostics(estimates=diagnostics.estimates, summary=diagnostics.summary)


def run_build_partition_plan(
    project: SchemaProject,
    viewmodel: RunCenterViewModel,
) -> list[PartitionPlanEntry]:
    return shared_run_commands.run_build_partition_plan(project, viewmodel)


def run_benchmark(
    project: SchemaProject,
    viewmodel: RunCenterViewModel,
    *,
    on_event: Callable[[RuntimeEvent], None] | None = None,
    cancel_requested: Callable[[], bool] | None = None,
) -> BenchmarkResult:
    return shared_run_commands.run_benchmark(
        project,
        viewmodel,
        on_event=on_event,
        cancel_requested=cancel_requested,
    )


def run_generation(
    project: SchemaProject,
    viewmodel: RunCenterViewModel,
    *,
    output_csv_folder: str | None = None,
    output_sqlite_path: str | None = None,
    on_event: Callable[[MultiprocessEvent], None] | None = None,
    cancel_requested: Callable[[], bool] | None = None,
    fallback_to_single_process: bool = False,
) -> MultiprocessRunResult:
    return shared_run_commands.run_generation_multiprocess(
        project,
        viewmodel,
        output_csv_folder=output_csv_folder,
        output_sqlite_path=output_sqlite_path,
        on_event=on_event,
        cancel_requested=cancel_requested,
        fallback_to_single_process=fallback_to_single_process,
    )
