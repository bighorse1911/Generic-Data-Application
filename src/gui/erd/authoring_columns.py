from __future__ import annotations

from typing import Any

from src.gui.erd.authoring_rename_refs import _replace_name_in_list, _replace_name_in_optional_value
from src.gui.erd.common import _erd_error, _parse_authoring_dtype, _parse_non_empty_name, _require_project
from src.schema_project_model import ColumnSpec, ForeignKeySpec, SchemaProject, TableSpec


def add_column_to_erd_project(
    project: Any,
    *,
    table_name_value: Any,
    column_name_value: Any,
    dtype_value: Any,
    primary_key: bool = False,
    nullable: bool = True,
) -> SchemaProject:
    current = _require_project(project)
    table_name = _parse_non_empty_name(
        table_name_value,
        field="Add column / Table",
        hint="choose the table where the column should be added",
    )
    column_name = _parse_non_empty_name(
        column_name_value,
        field="Add column / Name",
        hint="enter a non-empty column name",
    )

    table: TableSpec | None = None
    for candidate in current.tables:
        if candidate.table_name == table_name:
            table = candidate
            break
    if table is None:
        raise ValueError(
            _erd_error(
                "Add column / Table",
                f"table '{table_name}' was not found",
                "choose an existing table before adding columns",
            )
        )
    if any(c.name == column_name for c in table.columns):
        raise ValueError(
            _erd_error(
                "Add column / Name",
                f"column '{column_name}' already exists on table '{table_name}'",
                "choose a unique column name for this table",
            )
        )

    dtype = _parse_authoring_dtype(dtype_value, field="Add column / DType")

    wants_pk = bool(primary_key)
    nullable_value = bool(nullable)
    if wants_pk and dtype != "int":
        raise ValueError(
            _erd_error(
                "Add column / Primary key",
                f"primary key column '{column_name}' must be dtype=int",
                "set dtype='int' or disable the Primary key option",
            )
        )
    existing_pk = next((c for c in table.columns if c.primary_key), None)
    if wants_pk and existing_pk is not None:
        raise ValueError(
            _erd_error(
                "Add column / Primary key",
                f"table '{table_name}' already has primary key column '{existing_pk.name}'",
                "add this column as non-primary key or remove the existing PK first",
            )
        )
    if wants_pk:
        nullable_value = False

    next_columns = [
        *table.columns,
        ColumnSpec(
            name=column_name,
            dtype=dtype,
            nullable=nullable_value,
            primary_key=wants_pk,
        ),
    ]

    next_tables: list[TableSpec] = []
    for candidate in current.tables:
        if candidate.table_name == table_name:
            next_tables.append(
                TableSpec(
                    table_name=candidate.table_name,
                    columns=next_columns,
                    row_count=candidate.row_count,
                    business_key=candidate.business_key,
                    business_key_unique_count=candidate.business_key_unique_count,
                    business_key_static_columns=candidate.business_key_static_columns,
                    business_key_changing_columns=candidate.business_key_changing_columns,
                    scd_mode=candidate.scd_mode,
                    scd_tracked_columns=candidate.scd_tracked_columns,
                    scd_active_from_column=candidate.scd_active_from_column,
                    scd_active_to_column=candidate.scd_active_to_column,
                    correlation_groups=candidate.correlation_groups,
                )
            )
        else:
            next_tables.append(candidate)

    return SchemaProject(
        name=current.name,
        seed=current.seed,
        tables=next_tables,
        foreign_keys=list(current.foreign_keys),
        timeline_constraints=current.timeline_constraints,
        data_quality_profiles=current.data_quality_profiles,
        sample_profile_fits=current.sample_profile_fits,
        locale_identity_bundles=current.locale_identity_bundles,
    )


def update_column_in_erd_project(
    project: Any,
    *,
    table_name_value: Any,
    current_column_name_value: Any,
    new_column_name_value: Any,
    dtype_value: Any,
    primary_key: bool,
    nullable: bool,
) -> SchemaProject:
    current = _require_project(project)
    table_name = _parse_non_empty_name(
        table_name_value,
        field="Edit column / Table",
        hint="choose an existing table",
    )
    current_column_name = _parse_non_empty_name(
        current_column_name_value,
        field="Edit column / Current column",
        hint="choose an existing column",
    )
    new_column_name = _parse_non_empty_name(
        new_column_name_value,
        field="Edit column / Name",
        hint="enter a non-empty column name",
    )
    dtype = _parse_authoring_dtype(dtype_value, field="Edit column / DType")

    target_table: TableSpec | None = None
    for table in current.tables:
        if table.table_name == table_name:
            target_table = table
            break
    if target_table is None:
        raise ValueError(
            _erd_error(
                "Edit column / Table",
                f"table '{table_name}' was not found",
                "choose an existing table",
            )
        )

    current_column: ColumnSpec | None = None
    for column in target_table.columns:
        if column.name == current_column_name:
            current_column = column
            break
    if current_column is None:
        raise ValueError(
            _erd_error(
                "Edit column / Current column",
                f"column '{current_column_name}' was not found on table '{table_name}'",
                "choose an existing column",
            )
        )

    if new_column_name != current_column_name:
        if any(c.name == new_column_name for c in target_table.columns):
            raise ValueError(
                _erd_error(
                    "Edit column / Name",
                    f"column '{new_column_name}' already exists on table '{table_name}'",
                    "choose a unique column name for this table",
                )
            )

    wants_pk = bool(primary_key)
    nullable_value = bool(nullable)
    if wants_pk and dtype != "int":
        raise ValueError(
            _erd_error(
                "Edit column / Primary key",
                f"primary key column '{new_column_name}' must be dtype=int",
                "set dtype='int' or disable the Primary key option",
            )
        )
    other_pk = next(
        (c for c in target_table.columns if c.primary_key and c.name != current_column_name),
        None,
    )
    if wants_pk and other_pk is not None:
        raise ValueError(
            _erd_error(
                "Edit column / Primary key",
                f"table '{table_name}' already has primary key column '{other_pk.name}'",
                "disable Primary key on this edit or change the existing PK first",
            )
        )
    if wants_pk:
        nullable_value = False

    child_fk_refs = [
        fk
        for fk in current.foreign_keys
        if fk.child_table == table_name and fk.child_column == current_column_name
    ]
    parent_fk_refs = [
        fk
        for fk in current.foreign_keys
        if fk.parent_table == table_name and fk.parent_column == current_column_name
    ]

    if child_fk_refs and dtype != "int":
        raise ValueError(
            _erd_error(
                "Edit column / DType",
                f"column '{table_name}.{current_column_name}' is used as an FK child column",
                "keep dtype='int' for FK child columns or remove the relationship first",
            )
        )
    if child_fk_refs and wants_pk:
        raise ValueError(
            _erd_error(
                "Edit column / Primary key",
                f"column '{table_name}.{current_column_name}' is used as an FK child column",
                "child FK columns cannot be primary keys; disable Primary key for this column",
            )
        )
    if parent_fk_refs and not wants_pk:
        raise ValueError(
            _erd_error(
                "Edit column / Primary key",
                f"column '{table_name}.{current_column_name}' is referenced by FK relationships",
                "keep this column as primary key or remove dependent relationships first",
            )
        )

    next_columns: list[ColumnSpec] = []
    for column in target_table.columns:
        if column.name == current_column_name:
            next_columns.append(
                ColumnSpec(
                    name=new_column_name,
                    dtype=dtype,
                    nullable=nullable_value,
                    primary_key=wants_pk,
                    unique=column.unique,
                    min_value=column.min_value,
                    max_value=column.max_value,
                    choices=(list(column.choices) if column.choices is not None else None),
                    pattern=column.pattern,
                    generator=column.generator,
                    params=(dict(column.params) if isinstance(column.params, dict) else column.params),
                    depends_on=(list(column.depends_on) if column.depends_on is not None else None),
                )
            )
            continue

        next_depends_on = _replace_name_in_list(
            column.depends_on,
            old_name=current_column_name,
            new_name=new_column_name,
        )
        next_columns.append(
            ColumnSpec(
                name=column.name,
                dtype=column.dtype,
                nullable=column.nullable,
                primary_key=column.primary_key,
                unique=column.unique,
                min_value=column.min_value,
                max_value=column.max_value,
                choices=(list(column.choices) if column.choices is not None else None),
                pattern=column.pattern,
                generator=column.generator,
                params=(dict(column.params) if isinstance(column.params, dict) else column.params),
                depends_on=next_depends_on,
            )
        )

    next_tables: list[TableSpec] = []
    for table in current.tables:
        if table.table_name != table_name:
            next_tables.append(table)
            continue
        next_tables.append(
            TableSpec(
                table_name=table.table_name,
                columns=next_columns,
                row_count=table.row_count,
                business_key=_replace_name_in_list(
                    table.business_key,
                    old_name=current_column_name,
                    new_name=new_column_name,
                ),
                business_key_unique_count=table.business_key_unique_count,
                business_key_static_columns=_replace_name_in_list(
                    table.business_key_static_columns,
                    old_name=current_column_name,
                    new_name=new_column_name,
                ),
                business_key_changing_columns=_replace_name_in_list(
                    table.business_key_changing_columns,
                    old_name=current_column_name,
                    new_name=new_column_name,
                ),
                scd_mode=table.scd_mode,
                scd_tracked_columns=_replace_name_in_list(
                    table.scd_tracked_columns,
                    old_name=current_column_name,
                    new_name=new_column_name,
                ),
                scd_active_from_column=_replace_name_in_optional_value(
                    table.scd_active_from_column,
                    old_name=current_column_name,
                    new_name=new_column_name,
                ),
                scd_active_to_column=_replace_name_in_optional_value(
                    table.scd_active_to_column,
                    old_name=current_column_name,
                    new_name=new_column_name,
                ),
                correlation_groups=table.correlation_groups,
            )
        )

    next_foreign_keys: list[ForeignKeySpec] = []
    for fk in current.foreign_keys:
        next_foreign_keys.append(
            ForeignKeySpec(
                child_table=fk.child_table,
                child_column=(
                    new_column_name
                    if fk.child_table == table_name and fk.child_column == current_column_name
                    else fk.child_column
                ),
                parent_table=fk.parent_table,
                parent_column=(
                    new_column_name
                    if fk.parent_table == table_name and fk.parent_column == current_column_name
                    else fk.parent_column
                ),
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
    "add_column_to_erd_project",
    "update_column_in_erd_project",
]
