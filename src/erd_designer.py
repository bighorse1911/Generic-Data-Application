from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

from src.schema_project_io import load_project_from_json, save_project_to_json
from src.schema_project_model import ColumnSpec, ForeignKeySpec, SchemaProject, TableSpec


def _erd_error(field: str, issue: str, hint: str) -> str:
    return f"ERD Designer / {field}: {issue}. Fix: {hint}."


ERD_AUTHORING_DTYPES: tuple[str, ...] = (
    "int",
    "decimal",
    "text",
    "bool",
    "date",
    "datetime",
    "bytes",
)


def _parse_non_empty_name(value: Any, *, field: str, hint: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError(_erd_error(field, "value is required", hint))
    return value.strip()


def _parse_positive_int(value: Any, *, field: str, hint: str, allow_zero: bool = False) -> int:
    if isinstance(value, bool):
        raise ValueError(_erd_error(field, "must be an integer", hint))
    try:
        out = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(_erd_error(field, "must be an integer", hint)) from exc
    if allow_zero:
        if out < 0:
            raise ValueError(_erd_error(field, "must be >= 0", hint))
    elif out <= 0:
        raise ValueError(_erd_error(field, "must be > 0", hint))
    return out


def _parse_seed(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError(
            _erd_error(
                "Schema seed",
                "must be an integer",
                "enter a whole-number seed value (for example 12345)",
            )
        )
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _erd_error(
                "Schema seed",
                "must be an integer",
                "enter a whole-number seed value (for example 12345)",
            )
        ) from exc


def _require_project(project: Any) -> SchemaProject:
    if isinstance(project, SchemaProject):
        return project
    raise ValueError(
        _erd_error(
            "Schema state",
            "schema project is not initialized",
            "create a new schema or load an existing schema before editing",
        )
    )


def _parse_authoring_dtype(
    dtype_value: Any,
    *,
    field: str,
) -> str:
    if not isinstance(dtype_value, str) or dtype_value.strip() == "":
        raise ValueError(
            _erd_error(
                field,
                "dtype is required",
                f"choose one of: {', '.join(ERD_AUTHORING_DTYPES)}",
            )
        )
    dtype = dtype_value.strip().lower()
    if dtype == "float":
        raise ValueError(
            _erd_error(
                field,
                "dtype 'float' is deprecated for new GUI columns",
                "choose dtype='decimal' for new numeric columns",
            )
        )
    if dtype not in ERD_AUTHORING_DTYPES:
        raise ValueError(
            _erd_error(
                field,
                f"unsupported dtype '{dtype}'",
                f"choose one of: {', '.join(ERD_AUTHORING_DTYPES)}",
            )
        )
    return dtype


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
    return SchemaProject(name=name, seed=seed, tables=[], foreign_keys=[])


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
    )


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
                )
            )
        else:
            next_tables.append(candidate)

    return SchemaProject(
        name=current.name,
        seed=current.seed,
        tables=next_tables,
        foreign_keys=list(current.foreign_keys),
    )


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
    )


def _replace_name_in_list(values: list[str] | None, *, old_name: str, new_name: str) -> list[str] | None:
    if values is None:
        return None
    return [new_name if value == old_name else value for value in values]


def _replace_name_in_optional_value(value: str | None, *, old_name: str, new_name: str) -> str | None:
    if value is None:
        return None
    return new_name if value == old_name else value


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
            )
        )

    return SchemaProject(
        name=current.name,
        seed=current.seed,
        tables=next_tables,
        foreign_keys=next_foreign_keys,
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
            )
        )

    return SchemaProject(
        name=current.name,
        seed=current.seed,
        tables=next_tables,
        foreign_keys=next_foreign_keys,
    )


def export_schema_project_to_json(
    *,
    project: Any,
    output_path_value: Any,
) -> Path:
    current = _require_project(project)

    if not isinstance(output_path_value, str) or output_path_value.strip() == "":
        raise ValueError(
            _erd_error(
                "Schema export path",
                "output path is required",
                "choose a destination .json file path",
            )
        )

    output_path = Path(output_path_value.strip())
    if output_path.suffix.lower() != ".json":
        raise ValueError(
            _erd_error(
                "Schema export path",
                f"unsupported extension '{output_path.suffix or '<none>'}'",
                "use a .json output file extension",
            )
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        save_project_to_json(current, str(output_path))
    except ValueError as exc:
        raise ValueError(
            _erd_error(
                "Schema export",
                f"schema is invalid for export ({exc})",
                "fix schema validation issues and retry export",
            )
        ) from exc
    except OSError as exc:
        raise ValueError(
            _erd_error(
                "Schema export",
                f"failed to write schema JSON ({exc})",
                "check destination path permissions and retry",
            )
        ) from exc
    return output_path


@dataclass(frozen=True)
class ERDNode:
    table_name: str
    lines: list[str]
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class ERDEdge:
    parent_table: str
    parent_column: str
    child_table: str
    child_column: str


def load_project_schema_for_erd(path_value: Any) -> SchemaProject:
    if not isinstance(path_value, str) or path_value.strip() == "":
        raise ValueError(
            _erd_error(
                "Schema path",
                "path is required",
                "choose an existing schema project JSON file",
            )
        )

    path = Path(path_value.strip())
    if not path.exists():
        raise ValueError(
            _erd_error(
                "Schema path",
                f"path '{path}' does not exist",
                "choose an existing schema project JSON file",
            )
        )

    try:
        return load_project_from_json(str(path))
    except Exception as exc:
        raise ValueError(
            _erd_error(
                "Schema input",
                f"failed to load schema JSON from '{path}' ({exc})",
                "provide a valid schema project JSON file generated by this application",
            )
        ) from exc


def _fk_columns_by_table(project: SchemaProject) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for fk in project.foreign_keys:
        out.setdefault(fk.child_table, set()).add(fk.child_column)
    return out


def build_table_detail_lines(
    table: TableSpec,
    *,
    fk_columns: set[str],
    show_columns: bool,
    show_dtypes: bool,
) -> list[str]:
    if not show_columns:
        return []

    lines: list[str] = []
    for col in table.columns:
        tags: list[str] = []
        if col.primary_key:
            tags.append("PK")
        if col.name in fk_columns:
            tags.append("FK")
        tag_text = f"[{','.join(tags)}] " if tags else ""
        dtype_text = f": {col.dtype}" if show_dtypes else ""
        lines.append(f"{tag_text}{col.name}{dtype_text}")
    return lines


def _table_levels(project: SchemaProject) -> dict[str, int]:
    table_names = sorted(t.table_name for t in project.tables)
    parents_by_child: dict[str, set[str]] = {name: set() for name in table_names}
    for fk in project.foreign_keys:
        parents_by_child.setdefault(fk.child_table, set()).add(fk.parent_table)

    levels: dict[str, int] = {}
    for name in table_names:
        if not parents_by_child.get(name):
            levels[name] = 0

    progress = True
    while progress:
        progress = False
        for name in table_names:
            if name in levels:
                continue
            parents = parents_by_child.get(name, set())
            if parents and all(parent in levels for parent in parents):
                levels[name] = max(levels[parent] for parent in parents) + 1
                progress = True

    # Cycles should be rare/invalid; keep deterministic fallback layout.
    for name in table_names:
        levels.setdefault(name, 0)
    return levels


def build_erd_layout(
    project: SchemaProject,
    *,
    show_columns: bool,
    show_dtypes: bool,
    node_width: int = 300,
    header_height: int = 30,
    line_height: int = 18,
    margin: int = 32,
    column_gap: int = 110,
    row_gap: int = 24,
) -> tuple[list[ERDNode], list[ERDEdge], int, int]:
    table_map = {t.table_name: t for t in project.tables}
    levels = _table_levels(project)
    fk_columns_by_table = _fk_columns_by_table(project)

    names_by_level: dict[int, list[str]] = {}
    for table_name, level in levels.items():
        names_by_level.setdefault(level, []).append(table_name)
    for names in names_by_level.values():
        names.sort()

    nodes: list[ERDNode] = []
    max_y = margin
    max_level = max(levels.values(), default=0)

    for level in sorted(names_by_level.keys()):
        x = margin + level * (node_width + column_gap)
        y = margin
        for table_name in names_by_level[level]:
            table = table_map[table_name]
            lines = build_table_detail_lines(
                table,
                fk_columns=fk_columns_by_table.get(table_name, set()),
                show_columns=show_columns,
                show_dtypes=show_dtypes,
            )
            line_count = max(1, len(lines))
            height = header_height + 12 + (line_count * line_height)
            node = ERDNode(
                table_name=table_name,
                lines=lines,
                x=x,
                y=y,
                width=node_width,
                height=height,
            )
            nodes.append(node)
            y += height + row_gap
        max_y = max(max_y, y)

    edges = [
        ERDEdge(
            parent_table=fk.parent_table,
            parent_column=fk.parent_column,
            child_table=fk.child_table,
            child_column=fk.child_column,
        )
        for fk in sorted(
            project.foreign_keys,
            key=lambda fk: (fk.parent_table, fk.child_table, fk.parent_column, fk.child_column),
        )
    ]

    width = margin * 2 + (max_level + 1) * node_width + max_level * column_gap
    height = max(max_y + margin, margin * 2 + 200)
    return nodes, edges, width, height


def edge_label(edge: ERDEdge) -> str:
    return f"{edge.child_table}.{edge.child_column} -> {edge.parent_table}.{edge.parent_column}"


def node_anchor_y(node: ERDNode, *, table: TableSpec, column_name: str) -> int:
    # Keep relationship anchor near the related column when columns are visible.
    header_base = node.y + 30 + 6
    for idx, col in enumerate(table.columns):
        if col.name == column_name:
            return int(header_base + idx * 18)
    return int(node.y + node.height / 2)


def table_for_edge(
    edge: ERDEdge,
    *,
    table_map: dict[str, TableSpec],
) -> tuple[TableSpec, TableSpec]:
    try:
        parent = table_map[edge.parent_table]
        child = table_map[edge.child_table]
    except KeyError as exc:
        raise ValueError(
            _erd_error(
                "Relationships",
                f"edge references unknown table '{exc.args[0]}'",
                "ensure FK tables exist in schema input",
            )
        ) from exc
    return parent, child


def relation_lines(project: SchemaProject) -> list[ForeignKeySpec]:
    return sorted(
        project.foreign_keys,
        key=lambda fk: (fk.parent_table, fk.child_table, fk.parent_column, fk.child_column),
    )


def apply_node_position_overrides(
    nodes: list[ERDNode],
    *,
    positions: dict[str, tuple[int, int]] | None,
) -> list[ERDNode]:
    if not positions:
        return list(nodes)

    out: list[ERDNode] = []
    for node in nodes:
        moved = positions.get(node.table_name)
        if moved is None:
            out.append(node)
            continue
        out.append(
            ERDNode(
                table_name=node.table_name,
                lines=node.lines,
                x=int(moved[0]),
                y=int(moved[1]),
                width=node.width,
                height=node.height,
            )
        )
    return out


def compute_diagram_size(
    nodes: list[ERDNode],
    *,
    min_width: int,
    min_height: int,
    margin: int = 32,
) -> tuple[int, int]:
    max_right = max((node.x + node.width for node in nodes), default=0)
    max_bottom = max((node.y + node.height for node in nodes), default=0)
    return max(min_width, max_right + margin), max(min_height, max_bottom + margin)


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def build_erd_svg(
    project: SchemaProject,
    *,
    show_relationships: bool,
    show_columns: bool,
    show_dtypes: bool,
    node_positions: dict[str, tuple[int, int]] | None = None,
) -> str:
    nodes, edges, base_width, base_height = build_erd_layout(
        project,
        show_columns=show_columns,
        show_dtypes=show_dtypes,
    )
    nodes = apply_node_position_overrides(nodes, positions=node_positions)
    width, height = compute_diagram_size(nodes, min_width=base_width, min_height=base_height)
    node_by_table = {node.table_name: node for node in nodes}
    table_map = {table.table_name: table for table in project.tables}

    lines: list[str] = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
    )
    lines.append(f'  <rect x="0" y="0" width="{width}" height="{height}" fill="#f3f6fb" />')

    for node in nodes:
        x1 = node.x
        y1 = node.y
        x2 = node.x + node.width
        header_h = 30
        lines.append(
            f'  <rect x="{x1}" y="{y1}" width="{node.width}" height="{node.height}" fill="#ffffff" stroke="#556b8a" stroke-width="2" />'
        )
        lines.append(
            f'  <rect x="{x1}" y="{y1}" width="{node.width}" height="{header_h}" fill="#dae7f8" stroke="#556b8a" stroke-width="2" />'
        )
        lines.append(
            f'  <text x="{x1 + 8}" y="{y1 + 20}" font-family="Segoe UI, Arial, sans-serif" font-size="13" font-weight="bold" fill="#1a2a44">{_xml_escape(node.table_name)}</text>'
        )

        detail_lines = node.lines if node.lines else ["(columns hidden)"]
        y = y1 + 48
        for line in detail_lines:
            lines.append(
                f'  <text x="{x1 + 8}" y="{y}" font-family="Consolas, Courier New, monospace" font-size="11" fill="#27374d">{_xml_escape(line)}</text>'
            )
            y += 18
        _ = x2  # keep shape parity/readability

    if show_relationships:
        for edge in edges:
            parent_node = node_by_table.get(edge.parent_table)
            child_node = node_by_table.get(edge.child_table)
            if parent_node is None or child_node is None:
                continue
            try:
                parent_table, child_table = table_for_edge(edge, table_map=table_map)
            except ValueError:
                continue

            if show_columns:
                y1 = node_anchor_y(parent_node, table=parent_table, column_name=edge.parent_column)
                y2 = node_anchor_y(child_node, table=child_table, column_name=edge.child_column)
            else:
                y1 = int(parent_node.y + parent_node.height / 2)
                y2 = int(child_node.y + child_node.height / 2)

            x1 = parent_node.x + parent_node.width
            x2 = child_node.x
            mid_x = int((x1 + x2) / 2)
            path = f"M {x1} {y1} L {mid_x} {y1} L {mid_x} {y2} L {x2} {y2}"
            lines.append(
                f'  <path d="{path}" fill="none" stroke="#1f5a95" stroke-width="2" marker-end="url(#arrow)" />'
            )
            label = _xml_escape(edge_label(edge))
            lines.append(
                f'  <text x="{mid_x + 6}" y="{int((y1 + y2) / 2) - 7}" font-family="Segoe UI, Arial, sans-serif" font-size="10" fill="#1f5a95">{label}</text>'
            )

    lines.insert(
        3,
        '  <defs><marker id="arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#1f5a95" /></marker></defs>',
    )
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def _find_ghostscript_executable() -> str | None:
    candidates = [
        "gswin64c",
        "gswin32c",
        "gs",
    ]
    for name in candidates:
        resolved = shutil.which(name)
        if resolved:
            return resolved

    # Common Windows install roots as fallback.
    common_roots = [
        Path("C:/Program Files/gs"),
        Path("C:/Program Files (x86)/gs"),
    ]
    for root in common_roots:
        if not root.exists():
            continue
        for version_dir in sorted(root.glob("*"), reverse=True):
            candidate = version_dir / "bin" / "gswin64c.exe"
            if candidate.exists():
                return str(candidate)
            candidate = version_dir / "bin" / "gswin32c.exe"
            if candidate.exists():
                return str(candidate)
    return None


def _export_raster_with_ghostscript(
    *,
    output_path: Path,
    postscript_data: str,
    raster_format: str,
) -> None:
    gs = _find_ghostscript_executable()
    if gs is None:
        raise ValueError(
            _erd_error(
                "Export",
                f"{raster_format.upper()} export requires Ghostscript but it was not found",
                "install Ghostscript (gswin64c) or export as SVG",
            )
        )

    device = "pngalpha" if raster_format == "png" else "jpeg"
    with tempfile.NamedTemporaryFile(suffix=".ps", delete=False) as tmp:
        ps_path = Path(tmp.name)
        tmp.write(postscript_data.encode("utf-8"))

    cmd = [
        gs,
        "-dSAFER",
        "-dBATCH",
        "-dNOPAUSE",
        f"-sDEVICE={device}",
        "-r160",
        f"-sOutputFile={output_path}",
        str(ps_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    finally:
        try:
            ps_path.unlink()
        except OSError:
            pass

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        details = stderr.splitlines()[0] if stderr else f"ghostscript exit code {proc.returncode}"
        raise ValueError(
            _erd_error(
                "Export",
                f"failed to export {raster_format.upper()} ({details})",
                "verify Ghostscript is installed and retry, or export as SVG",
            )
        )


def export_erd_file(
    *,
    output_path_value: Any,
    svg_text: str,
    postscript_data: str | None = None,
) -> Path:
    if not isinstance(output_path_value, str) or output_path_value.strip() == "":
        raise ValueError(
            _erd_error(
                "Export path",
                "output path is required",
                "choose a file path ending in .svg, .png, .jpg, or .jpeg",
            )
        )
    output_path = Path(output_path_value.strip())
    ext = output_path.suffix.lower()
    if ext not in {".svg", ".png", ".jpg", ".jpeg"}:
        raise ValueError(
            _erd_error(
                "Export format",
                f"unsupported extension '{ext or '<none>'}'",
                "use .svg, .png, .jpg, or .jpeg",
            )
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if ext == ".svg":
        output_path.write_text(svg_text, encoding="utf-8")
        return output_path

    if postscript_data is None or postscript_data.strip() == "":
        raise ValueError(
            _erd_error(
                "Export source",
                f"{ext[1:].upper()} export requires rendered canvas postscript data",
                "render the ERD before exporting",
            )
        )
    _export_raster_with_ghostscript(
        output_path=output_path,
        postscript_data=postscript_data,
        raster_format="png" if ext == ".png" else "jpeg",
    )
    return output_path
