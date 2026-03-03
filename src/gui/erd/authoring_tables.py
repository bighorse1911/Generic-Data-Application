from __future__ import annotations

from typing import Any

from src.gui.erd.authoring_rename_refs import _replace_name_in_list, _replace_name_in_optional_value
from src.gui.erd.common import (
    _erd_error,
    _parse_non_empty_name,
    _parse_positive_int,
    _parse_seed,
    _require_project,
)
from src.schema_project_model import ForeignKeySpec, SchemaProject, TableSpec


def new_erd_schema_project(
    *,
    name_value: Any,
    seed_value: Any = 12345,
) -> SchemaProject:
    name = _parse_non_empty_name(
        name_value,
        field="Schema name",
        hint="enter a non-empty schema project name",
    )
    seed = _parse_seed(seed_value)
    return SchemaProject(
        name=name,
        seed=seed,
        tables=[],
        foreign_keys=[],
        timeline_constraints=None,
        data_quality_profiles=None,
        sample_profile_fits=None,
        locale_identity_bundles=None,
    )


def add_table_to_erd_project(
    project: Any,
    *,
    table_name_value: Any,
    row_count_value: Any = 100,
) -> SchemaProject:
    current = _require_project(project)
    table_name = _parse_non_empty_name(
        table_name_value,
        field="Add table / Name",
        hint="enter a non-empty table name",
    )
    if any(t.table_name == table_name for t in current.tables):
        raise ValueError(
            _erd_error(
                "Add table / Name",
                f"table '{table_name}' already exists",
                "choose a unique table name",
            )
        )
    row_count = _parse_positive_int(
        row_count_value,
        field="Add table / Row count",
        hint="enter a positive integer row count",
    )
    new_table = TableSpec(table_name=table_name, row_count=row_count, columns=[])
    return SchemaProject(
        name=current.name,
        seed=current.seed,
        tables=[*current.tables, new_table],
        foreign_keys=list(current.foreign_keys),
        timeline_constraints=current.timeline_constraints,
        data_quality_profiles=current.data_quality_profiles,
        sample_profile_fits=current.sample_profile_fits,
        locale_identity_bundles=current.locale_identity_bundles,
    )


def update_table_in_erd_project(
    project: Any,
    *,
    current_table_name_value: Any,
    new_table_name_value: Any,
    row_count_value: Any,
) -> SchemaProject:
    current = _require_project(project)
    current_table_name = _parse_non_empty_name(
        current_table_name_value,
        field="Edit table / Current table",
        hint="choose an existing table to edit",
    )
    new_table_name = _parse_non_empty_name(
        new_table_name_value,
        field="Edit table / New name",
        hint="enter a non-empty table name",
    )
    row_count = _parse_positive_int(
        row_count_value,
        field="Edit table / Row count",
        hint="enter a positive integer row count",
    )

    target_table: TableSpec | None = None
    for table in current.tables:
        if table.table_name == current_table_name:
            target_table = table
            break
    if target_table is None:
        raise ValueError(
            _erd_error(
                "Edit table / Current table",
                f"table '{current_table_name}' was not found",
                "choose an existing table to edit",
            )
        )

    if new_table_name != current_table_name:
        if any(table.table_name == new_table_name for table in current.tables):
            raise ValueError(
                _erd_error(
                    "Edit table / New name",
                    f"table '{new_table_name}' already exists",
                    "choose a unique table name",
                )
            )

    next_tables: list[TableSpec] = []
    for table in current.tables:
        if table.table_name != current_table_name:
            next_tables.append(table)
            continue
        next_tables.append(
            TableSpec(
                table_name=new_table_name,
                columns=list(table.columns),
                row_count=row_count,
                business_key=table.business_key,
                business_key_unique_count=table.business_key_unique_count,
                business_key_static_columns=table.business_key_static_columns,
                business_key_changing_columns=table.business_key_changing_columns,
                scd_mode=table.scd_mode,
                scd_tracked_columns=table.scd_tracked_columns,
                scd_active_from_column=table.scd_active_from_column,
                scd_active_to_column=table.scd_active_to_column,
                correlation_groups=table.correlation_groups,
            )
        )

    next_foreign_keys: list[ForeignKeySpec] = []
    for fk in current.foreign_keys:
        next_foreign_keys.append(
            ForeignKeySpec(
                child_table=new_table_name if fk.child_table == current_table_name else fk.child_table,
                child_column=fk.child_column,
                parent_table=new_table_name if fk.parent_table == current_table_name else fk.parent_table,
                parent_column=fk.parent_column,
                min_children=fk.min_children,
                max_children=fk.max_children,
                parent_selection=fk.parent_selection,
                child_count_distribution=fk.child_count_distribution,
            )
        )

    return SchemaProject(
        name=current.name,
        seed=current.seed,
        tables=next_tables,
        foreign_keys=next_foreign_keys,
        timeline_constraints=current.timeline_constraints,
        data_quality_profiles=current.data_quality_profiles,
        sample_profile_fits=current.sample_profile_fits,
        locale_identity_bundles=current.locale_identity_bundles,
    )


__all__ = [
    "new_erd_schema_project",
    "add_table_to_erd_project",
    "update_table_in_erd_project",
    "_replace_name_in_list",
    "_replace_name_in_optional_value",
]
