from __future__ import annotations

from typing import Any

from src.gui.erd.common import _erd_error, _parse_non_empty_name, _parse_positive_int, _require_project
from src.schema_project_model import ForeignKeySpec, SchemaProject


def add_relationship_to_erd_project(
    project: Any,
    *,
    child_table_value: Any,
    child_column_value: Any,
    parent_table_value: Any,
    parent_column_value: Any,
    min_children_value: Any = 1,
    max_children_value: Any = 3,
) -> SchemaProject:
    current = _require_project(project)
    child_table_name = _parse_non_empty_name(
        child_table_value,
        field="Add relationship / Child table",
        hint="choose an existing child table",
    )
    child_column_name = _parse_non_empty_name(
        child_column_value,
        field="Add relationship / Child column",
        hint="choose an existing child column",
    )
    parent_table_name = _parse_non_empty_name(
        parent_table_value,
        field="Add relationship / Parent table",
        hint="choose an existing parent table",
    )
    parent_column_name = _parse_non_empty_name(
        parent_column_value,
        field="Add relationship / Parent column",
        hint="choose an existing parent column",
    )

    table_map = {table.table_name: table for table in current.tables}
    child_table = table_map.get(child_table_name)
    if child_table is None:
        raise ValueError(
            _erd_error(
                "Add relationship / Child table",
                f"table '{child_table_name}' was not found",
                "choose an existing child table",
            )
        )
    parent_table = table_map.get(parent_table_name)
    if parent_table is None:
        raise ValueError(
            _erd_error(
                "Add relationship / Parent table",
                f"table '{parent_table_name}' was not found",
                "choose an existing parent table",
            )
        )

    child_cols = {c.name: c for c in child_table.columns}
    parent_cols = {c.name: c for c in parent_table.columns}
    child_col = child_cols.get(child_column_name)
    if child_col is None:
        raise ValueError(
            _erd_error(
                "Add relationship / Child column",
                f"column '{child_column_name}' was not found on table '{child_table_name}'",
                "choose an existing child column",
            )
        )
    parent_col = parent_cols.get(parent_column_name)
    if parent_col is None:
        raise ValueError(
            _erd_error(
                "Add relationship / Parent column",
                f"column '{parent_column_name}' was not found on table '{parent_table_name}'",
                "choose an existing parent column",
            )
        )
    if child_col.dtype != "int":
        raise ValueError(
            _erd_error(
                "Add relationship / Child column",
                f"column '{child_table_name}.{child_column_name}' must be dtype=int for FK",
                "change the child column dtype to int or choose another column",
            )
        )
    if child_col.primary_key:
        raise ValueError(
            _erd_error(
                "Add relationship / Child column",
                f"column '{child_table_name}.{child_column_name}' is a primary key",
                "choose a non-primary-key child column for FK relationships",
            )
        )
    if not parent_col.primary_key:
        raise ValueError(
            _erd_error(
                "Add relationship / Parent column",
                f"column '{parent_table_name}.{parent_column_name}' must be primary key",
                "choose the parent table primary-key column",
            )
        )

    min_children = _parse_positive_int(
        min_children_value,
        field="Add relationship / Min children",
        hint="enter a positive integer min_children value",
    )
    max_children = _parse_positive_int(
        max_children_value,
        field="Add relationship / Max children",
        hint="enter a positive integer max_children value",
    )
    if min_children > max_children:
        raise ValueError(
            _erd_error(
                "Add relationship / Child cardinality",
                "min_children cannot exceed max_children",
                "set min_children <= max_children",
            )
        )

    for fk in current.foreign_keys:
        if (
            fk.child_table == child_table_name
            and fk.child_column == child_column_name
            and fk.parent_table == parent_table_name
            and fk.parent_column == parent_column_name
        ):
            raise ValueError(
                _erd_error(
                    "Add relationship",
                    (
                        "relationship "
                        f"'{child_table_name}.{child_column_name} -> "
                        f"{parent_table_name}.{parent_column_name}' already exists"
                    ),
                    "remove the duplicate or choose different table/column mapping",
                )
            )

    next_fk = ForeignKeySpec(
        child_table=child_table_name,
        child_column=child_column_name,
        parent_table=parent_table_name,
        parent_column=parent_column_name,
        min_children=min_children,
        max_children=max_children,
    )
    return SchemaProject(
        name=current.name,
        seed=current.seed,
        tables=list(current.tables),
        foreign_keys=[*current.foreign_keys, next_fk],
        timeline_constraints=current.timeline_constraints,
        data_quality_profiles=current.data_quality_profiles,
        sample_profile_fits=current.sample_profile_fits,
        locale_identity_bundles=current.locale_identity_bundles,
    )


__all__ = [
    "add_relationship_to_erd_project",
]
