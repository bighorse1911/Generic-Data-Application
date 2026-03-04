from __future__ import annotations

import copy
import json
from dataclasses import asdict
from pathlib import Path
from typing import Mapping

from src.generator_project import generate_project_rows
from src.gui_schema_shared import DTYPES, valid_generators_for_dtype
from src.gui_v2.generator_forms import (
    GeneratorFormState,
    format_field_value,
    parse_field_text,
    split_form_state,
    visible_fields_for,
)
from src.gui_v2.schema_design_modes import (
    SchemaDesignMode,
    allowed_generators_for_mode,
    is_mode_downgrade,
    normalize_schema_design_mode,
)
from src.performance_scaling import PerformanceProfile, run_generation_with_strategy
from src.schema_project_io import load_project_from_json, save_project_to_json
from src.schema_project_model import (
    ColumnSpec,
    ForeignKeySpec,
    SchemaProject,
    TableSpec,
    validate_project,
)


def _error(location: str, issue: str, hint: str) -> str:
    return f"{location}: {issue}. Fix: {hint}."


class PyQtSchemaProjectController:
    """Pure-Python model/controller for the optional PyQt experiment."""

    def __init__(self, project: SchemaProject | None = None, *, history_limit: int = 100) -> None:
        self._history_limit = max(10, int(history_limit))
        self._undo_stack: list[SchemaProject] = []
        self._redo_stack: list[SchemaProject] = []
        self.preview_rows: dict[str, list[dict[str, object]]] = {}
        self.schema_design_mode: SchemaDesignMode = normalize_schema_design_mode("simple")
        self.project = copy.deepcopy(project) if project is not None else self._default_project()

    @staticmethod
    def _default_project() -> SchemaProject:
        return SchemaProject(
            name="pyqt_schema_project_experiment",
            seed=12345,
            tables=[
                TableSpec(
                    table_name="entities",
                    row_count=100,
                    columns=[ColumnSpec("entity_id", "int", nullable=False, primary_key=True)],
                )
            ],
            foreign_keys=[],
        )

    def _push_history(self) -> None:
        self._undo_stack.append(copy.deepcopy(self.project))
        if len(self._undo_stack) > self._history_limit:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _apply(self, project: SchemaProject, *, record_undo: bool = True) -> None:
        if record_undo:
            self._push_history()
        self.project = copy.deepcopy(project)
        self.preview_rows = {}

    def _project_with(self, **overrides: object) -> SchemaProject:
        payload = {
            "name": self.project.name,
            "seed": self.project.seed,
            "tables": list(self.project.tables),
            "foreign_keys": list(self.project.foreign_keys),
            "timeline_constraints": self.project.timeline_constraints,
            "data_quality_profiles": self.project.data_quality_profiles,
            "sample_profile_fits": self.project.sample_profile_fits,
            "locale_identity_bundles": self.project.locale_identity_bundles,
        }
        payload.update(overrides)
        return SchemaProject(**payload)

    @staticmethod
    def _table_with(table: TableSpec, **overrides: object) -> TableSpec:
        payload = {
            "table_name": table.table_name,
            "columns": list(table.columns),
            "row_count": table.row_count,
            "business_key": table.business_key,
            "business_key_unique_count": table.business_key_unique_count,
            "business_key_static_columns": table.business_key_static_columns,
            "business_key_changing_columns": table.business_key_changing_columns,
            "scd_mode": table.scd_mode,
            "scd_tracked_columns": table.scd_tracked_columns,
            "scd_active_from_column": table.scd_active_from_column,
            "scd_active_to_column": table.scd_active_to_column,
            "correlation_groups": table.correlation_groups,
        }
        payload.update(overrides)
        return TableSpec(**payload)

    def _table_index(self, table_name: str) -> int:
        for idx, table in enumerate(self.project.tables):
            if table.table_name == table_name:
                return idx
        raise ValueError(_error("Table editor", f"unknown table '{table_name}'", "choose an existing table"))

    def _column_index(self, table: TableSpec, column_name: str) -> int:
        for idx, column in enumerate(table.columns):
            if column.name == column_name:
                return idx
        raise ValueError(
            _error(
                f"Table '{table.table_name}' / Column editor",
                f"unknown column '{column_name}'",
                "select an existing column",
            )
        )

    @staticmethod
    def _csv_tokens(raw: str) -> list[str]:
        return [token.strip() for token in raw.split(",") if token.strip()]

    @staticmethod
    def _json_object(raw: str, *, location: str) -> dict[str, object] | None:
        text = raw.strip()
        if not text:
            return None
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                _error(location, f"invalid JSON ({exc.msg} at {exc.lineno}:{exc.colno})", "fix JSON object syntax")
            ) from exc
        if not isinstance(value, dict):
            raise ValueError(_error(location, "expected a JSON object", "provide an object value"))
        return value

    @staticmethod
    def _json_list(raw: str, *, location: str) -> list[dict[str, object]] | None:
        text = raw.strip()
        if not text:
            return None
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                _error(location, f"invalid JSON ({exc.msg} at {exc.lineno}:{exc.colno})", "fix JSON list syntax")
            ) from exc
        if not isinstance(value, list):
            raise ValueError(_error(location, "expected a JSON list", "provide a list of objects"))
        out: list[dict[str, object]] = []
        for idx, item in enumerate(value):
            if not isinstance(item, dict):
                raise ValueError(_error(location, f"item {idx} is not an object", "use object entries only"))
            out.append(dict(item))
        return out

    @staticmethod
    def _normalize_dtype(dtype: str, *, allow_legacy_float: bool = False) -> str:
        value = dtype.strip().lower()
        if value == "float" and not allow_legacy_float:
            raise ValueError(
                _error("Column editor / dtype", "dtype 'float' is deprecated for new GUI columns", "use 'decimal' instead")
            )
        allowed = set(DTYPES) | {"float"}
        if value not in allowed:
            raise ValueError(_error("Column editor / dtype", f"unsupported dtype '{dtype}'", f"choose one of: {', '.join(sorted(allowed))}"))
        return value

    def build_column_spec(
        self,
        *,
        name: str,
        dtype: str,
        nullable: bool = True,
        primary_key: bool = False,
        unique: bool = False,
        min_value: float | None = None,
        max_value: float | None = None,
        choices_csv: str = "",
        pattern: str = "",
        generator: str | None = None,
        params_json: str = "",
        depends_on_csv: str = "",
        allow_legacy_float: bool = False,
    ) -> ColumnSpec:
        col_name = name.strip()
        if not col_name:
            raise ValueError(_error("Column editor / Name", "column name is required", "enter a non-empty name"))
        dtype_value = self._normalize_dtype(dtype, allow_legacy_float=allow_legacy_float)
        if primary_key and dtype_value != "int":
            raise ValueError(_error(f"Column '{col_name}'", "primary key must use dtype 'int'", "set dtype='int'"))
        params = self._json_object(params_json, location=f"Column '{col_name}' / generator params")
        depends_on = self._csv_tokens(depends_on_csv) or None
        if primary_key and depends_on:
            raise ValueError(_error(f"Column '{col_name}'", "primary key cannot depend on columns", "clear depends_on"))
        return ColumnSpec(
            name=col_name,
            dtype=dtype_value,
            nullable=False if primary_key else bool(nullable),
            primary_key=bool(primary_key),
            unique=bool(unique),
            min_value=min_value,
            max_value=max_value,
            choices=self._csv_tokens(choices_csv) or None,
            pattern=pattern.strip() or None,
            generator=(generator or "").strip() or None,
            params=params,
            depends_on=depends_on,
        )

    def set_project_metadata(self, *, name: str, seed: int) -> None:
        project_name = name.strip()
        if not project_name:
            raise ValueError(_error("Project panel / Name", "project name is required", "enter a non-empty project name"))
        self._apply(self._project_with(name=project_name, seed=int(seed)))

    def set_project_level_json(
        self,
        *,
        timeline_constraints_json: str,
        data_quality_profiles_json: str,
        sample_profile_fits_json: str,
        locale_identity_bundles_json: str,
    ) -> None:
        self._apply(
            self._project_with(
                timeline_constraints=self._json_list(timeline_constraints_json, location="Project panel / Timeline constraints JSON"),
                data_quality_profiles=self._json_list(data_quality_profiles_json, location="Project panel / Data quality profiles JSON"),
                sample_profile_fits=self._json_list(sample_profile_fits_json, location="Project panel / Sample profile fits JSON"),
                locale_identity_bundles=self._json_list(locale_identity_bundles_json, location="Project panel / Locale identity bundles JSON"),
            )
        )

    def project_level_json_text(self) -> dict[str, str]:
        return {
            "timeline_constraints": json.dumps(self.project.timeline_constraints or [], indent=2),
            "data_quality_profiles": json.dumps(self.project.data_quality_profiles or [], indent=2),
            "sample_profile_fits": json.dumps(self.project.sample_profile_fits or [], indent=2),
            "locale_identity_bundles": json.dumps(self.project.locale_identity_bundles or [], indent=2),
        }

    def load_project(self, path: str | Path) -> SchemaProject:
        loaded = load_project_from_json(str(path))
        self._apply(loaded)
        return self.project

    def save_project(self, path: str | Path) -> None:
        validate_project(self.project)
        save_project_to_json(self.project, str(path))

    def table_names(self) -> list[str]:
        return [table.table_name for table in self.project.tables]

    def table_rows(self) -> list[dict[str, object]]:
        return [
            {
                "table_name": table.table_name,
                "row_count": table.row_count,
                "column_count": len(table.columns),
                "scd_mode": table.scd_mode or "",
            }
            for table in self.project.tables
        ]

    def add_table(self, *, table_name: str, row_count: int = 100) -> None:
        name = table_name.strip()
        if not name:
            raise ValueError(_error("Table editor / Name", "table name is required", "enter a non-empty table name"))
        if name in set(self.table_names()):
            raise ValueError(_error("Table editor / Name", f"table '{name}' already exists", "choose a unique table name"))
        table = TableSpec(
            table_name=name,
            row_count=max(1, int(row_count)),
            columns=[ColumnSpec(f"{name}_id", "int", nullable=False, primary_key=True)],
        )
        self._apply(self._project_with(tables=list(self.project.tables) + [table]))

    def remove_table(self, table_name: str) -> None:
        idx = self._table_index(table_name)
        tables = [table for i, table in enumerate(self.project.tables) if i != idx]
        fks = [fk for fk in self.project.foreign_keys if fk.child_table != table_name and fk.parent_table != table_name]
        if not tables:
            tables = [
                TableSpec(
                    table_name="entities",
                    row_count=100,
                    columns=[ColumnSpec("entity_id", "int", nullable=False, primary_key=True)],
                )
            ]
        self._apply(self._project_with(tables=tables, foreign_keys=fks))

    def table_column_names(self, table_name: str) -> list[str]:
        return [column.name for column in self.project.tables[self._table_index(table_name)].columns]

    def column_rows(self, table_name: str) -> list[dict[str, object]]:
        table = self.project.tables[self._table_index(table_name)]
        return [
            {
                "name": c.name,
                "dtype": c.dtype,
                "nullable": c.nullable,
                "primary_key": c.primary_key,
                "unique": c.unique,
                "generator": c.generator or "",
                "depends_on": ", ".join(c.depends_on or []),
            }
            for c in table.columns
        ]

    def add_column(self, *, table_name: str, column: ColumnSpec) -> None:
        idx = self._table_index(table_name)
        table = self.project.tables[idx]
        if column.name in {c.name for c in table.columns}:
            raise ValueError(_error(f"Table '{table_name}' / Column editor", f"column '{column.name}' already exists", "use a unique column name"))
        tables = list(self.project.tables)
        tables[idx] = self._table_with(table, columns=list(table.columns) + [column])
        self._apply(self._project_with(tables=tables))

    def update_column(self, *, table_name: str, original_name: str, column: ColumnSpec) -> None:
        table_idx = self._table_index(table_name)
        table = self.project.tables[table_idx]
        col_idx = self._column_index(table, original_name)
        if column.name != original_name and column.name in {c.name for c in table.columns}:
            raise ValueError(_error(f"Table '{table_name}' / Column editor", f"column '{column.name}' already exists", "use a unique column name"))
        updated_columns = list(table.columns)
        updated_columns[col_idx] = column
        tables = list(self.project.tables)
        tables[table_idx] = self._table_with(table, columns=updated_columns)
        fks = list(self.project.foreign_keys)
        if column.name != original_name:
            fks = [
                ForeignKeySpec(
                    child_table=fk.child_table,
                    child_column=column.name if fk.child_table == table_name and fk.child_column == original_name else fk.child_column,
                    parent_table=fk.parent_table,
                    parent_column=column.name if fk.parent_table == table_name and fk.parent_column == original_name else fk.parent_column,
                    min_children=fk.min_children,
                    max_children=fk.max_children,
                    parent_selection=fk.parent_selection,
                    child_count_distribution=fk.child_count_distribution,
                )
                for fk in self.project.foreign_keys
            ]
        self._apply(self._project_with(tables=tables, foreign_keys=fks))

    def remove_column(self, *, table_name: str, column_name: str) -> None:
        table_idx = self._table_index(table_name)
        table = self.project.tables[table_idx]
        col_idx = self._column_index(table, column_name)
        target = table.columns[col_idx]
        if target.primary_key and len([c for c in table.columns if c.primary_key]) <= 1:
            raise ValueError(_error(f"Table '{table_name}' / Column editor", "cannot remove the only primary key", "add another primary key first"))
        for fk in self.project.foreign_keys:
            if (fk.child_table == table_name and fk.child_column == column_name) or (fk.parent_table == table_name and fk.parent_column == column_name):
                raise ValueError(_error(f"Table '{table_name}' / Column editor", f"column '{column_name}' is referenced by FK", "remove or edit FK first"))
        tables = list(self.project.tables)
        tables[table_idx] = self._table_with(table, columns=[c for i, c in enumerate(table.columns) if i != col_idx])
        self._apply(self._project_with(tables=tables))

    def foreign_key_rows(self) -> list[dict[str, object]]:
        return [
            {
                "index": idx,
                "child_table": fk.child_table,
                "child_column": fk.child_column,
                "parent_table": fk.parent_table,
                "parent_column": fk.parent_column,
                "min_children": fk.min_children,
                "max_children": fk.max_children,
            }
            for idx, fk in enumerate(self.project.foreign_keys)
        ]

    def add_foreign_key(
        self,
        *,
        child_table: str,
        child_column: str,
        parent_table: str,
        parent_column: str,
        min_children: int,
        max_children: int,
        parent_selection_json: str = "",
        child_count_distribution_json: str = "",
    ) -> None:
        child_table = child_table.strip()
        child_column = child_column.strip()
        parent_table = parent_table.strip()
        parent_column = parent_column.strip()
        if child_table not in set(self.table_names()) or parent_table not in set(self.table_names()):
            raise ValueError(_error("Relationships panel", "unknown child/parent table", "select existing tables"))
        if child_column not in set(self.table_column_names(child_table)):
            raise ValueError(_error("Relationships panel / Child column", f"column '{child_column}' missing", "select an existing child column"))
        if parent_column not in set(self.table_column_names(parent_table)):
            raise ValueError(_error("Relationships panel / Parent column", f"column '{parent_column}' missing", "select an existing parent column"))
        fk = ForeignKeySpec(
            child_table=child_table,
            child_column=child_column,
            parent_table=parent_table,
            parent_column=parent_column,
            min_children=int(min_children),
            max_children=int(max_children),
            parent_selection=self._json_object(parent_selection_json, location="Relationships panel / Parent selection JSON"),
            child_count_distribution=self._json_object(child_count_distribution_json, location="Relationships panel / Child count distribution JSON"),
        )
        self._apply(self._project_with(foreign_keys=list(self.project.foreign_keys) + [fk]))

    def remove_foreign_key(self, index: int) -> None:
        rows = self.foreign_key_rows()
        if index < 0 or index >= len(rows):
            raise ValueError(_error("Relationships panel", f"foreign key index {index} out of range", "select an existing relationship"))
        self._apply(self._project_with(foreign_keys=[fk for i, fk in enumerate(self.project.foreign_keys) if i != index]))

    def validate_current(self) -> tuple[bool, str]:
        try:
            validate_project(self.project)
        except ValueError as exc:
            return False, str(exc)
        return True, "Schema project validation: project is valid. Fix: no action required."

    def generate_preview(self, *, row_limit: int = 500) -> dict[str, list[dict[str, object]]]:
        rows = generate_project_rows(self.project)
        limit = max(0, int(row_limit))
        if limit > 0:
            rows = {table_name: list(table_rows[:limit]) for table_name, table_rows in rows.items()}
        self.preview_rows = rows
        return rows

    def preview_table_names(self) -> list[str]:
        return sorted(self.preview_rows.keys()) if self.preview_rows else []

    def preview_rows_for_table(self, table_name: str) -> list[dict[str, object]]:
        return list(self.preview_rows.get(table_name, []))

    def export_csv(self, output_folder: str) -> dict[str, str]:
        result = run_generation_with_strategy(self.project, PerformanceProfile(output_mode="csv"), output_csv_folder=output_folder)
        return dict(result.csv_paths)

    def export_sqlite(self, sqlite_path: str) -> dict[str, int]:
        result = run_generation_with_strategy(self.project, PerformanceProfile(output_mode="sqlite"), output_sqlite_path=sqlite_path)
        return dict(result.sqlite_counts)

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        self._redo_stack.append(copy.deepcopy(self.project))
        self.project = copy.deepcopy(self._undo_stack.pop())
        self.preview_rows = {}
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        self._undo_stack.append(copy.deepcopy(self.project))
        self.project = copy.deepcopy(self._redo_stack.pop())
        self.preview_rows = {}
        return True

    def set_schema_design_mode(self, raw_mode: object) -> str:
        prev = self.schema_design_mode
        cur = normalize_schema_design_mode(raw_mode)
        self.schema_design_mode = cur
        if is_mode_downgrade(prev, cur):
            return "Schema design mode downgraded. Preserved hidden advanced values and out-of-mode generator selections."
        return f"Schema design mode set to '{cur}'."

    def generator_options_for_dtype(self, dtype: str, *, current_generator: str = "") -> list[str]:
        options = valid_generators_for_dtype(dtype)
        allowlist = set(allowed_generators_for_mode(self.schema_design_mode))
        filtered = [g for g in options if g in allowlist or g == ""]
        if current_generator and current_generator not in filtered:
            filtered.append(current_generator)
        return filtered

    def split_generator_form_state(self, *, generator_id: str, dtype: str, params_json: str) -> GeneratorFormState:
        params = self._json_object(params_json, location="Column editor / generator params")
        return split_form_state(generator_id, dtype=dtype, params=params)

    def merge_generator_form_values(
        self,
        *,
        generator_id: str,
        dtype: str,
        params_json: str,
        form_values: Mapping[str, str],
    ) -> dict[str, object]:
        state = self.split_generator_form_state(generator_id=generator_id, dtype=dtype, params_json=params_json)
        known = dict(state.known_params)
        errors: list[str] = []
        for spec in visible_fields_for(generator_id, dtype=dtype):
            raw = form_values.get(spec.field_id)
            if raw is None:
                continue
            if raw.strip() == "":
                if spec.required:
                    errors.append(f"{spec.label} is required")
                else:
                    known.pop(spec.field_id, None)
                continue
            try:
                parsed = parse_field_text(spec, raw)
            except ValueError as exc:
                errors.append(f"{spec.label}: {exc}")
                continue
            if parsed is None:
                known.pop(spec.field_id, None)
            else:
                known[spec.field_id] = parsed
        if errors:
            raise ValueError(_error("Column editor / structured generator form", "; ".join(errors), "correct form values"))
        for spec in visible_fields_for(generator_id, dtype=dtype):
            if spec.required and spec.field_id not in known:
                raise ValueError(_error("Column editor / structured generator form", f"missing required field '{spec.label}'", "provide all required fields"))
        merged = dict(state.passthrough_params)
        merged.update(known)
        return merged

    def format_generator_field_value(self, field_id: str, *, generator_id: str, dtype: str, params: Mapping[str, object]) -> str:
        for spec in visible_fields_for(generator_id, dtype=dtype):
            if spec.field_id == field_id:
                return format_field_value(spec, params.get(field_id))
        return ""

    def project_as_json_text(self) -> str:
        return json.dumps(asdict(self.project), indent=2)


__all__ = ["PyQtSchemaProjectController"]
