"""Internal orchestration for project row generation."""

from __future__ import annotations

import logging
import random
from typing import Callable

from src.generators import reset_runtime_generator_state
from src.generation.common import _runtime_error, _stable_subseed
from src.generation.correlation import _apply_table_correlation_groups
from src.generation.dependency import _dependency_order
from src.generation.fk_assignment import _allocate_fk_child_counts, _build_fk_parent_weights, _compile_fk_distribution_weights, _fk_parent_rows_and_ids, _normalize_fk_child_count_distribution, _sample_requested_fk_extras
from src.generation.locale_identity import _apply_table_locale_identity_bundles, _compile_locale_identity_bundles
from src.generation.profile_fit import _resolve_sample_profile_fits
from src.generation.quality_profiles import _apply_table_data_quality_profiles, _compile_data_quality_profiles
from src.generation.scd import _apply_business_key_and_scd, _table_pk_col_name
from src.generation.timeline import _compile_timeline_constraints, _enforce_table_timeline_constraints
from src.generation.value_generation import _gen_value, _order_columns_by_dependencies
from src.schema_project_model import ForeignKeySpec, SchemaProject, validate_project

def _compile_parent_cache_columns(
    project: SchemaProject,
    *,
    compiled_timeline_constraints: dict[str, list[dict[str, object]]],
) -> dict[str, set[str]]:
    required_by_table: dict[str, set[str]] = {}
    for fk in project.foreign_keys:
        cols = required_by_table.setdefault(fk.parent_table, set())
        cols.add(fk.parent_column)
        raw_profile = fk.parent_selection
        if isinstance(raw_profile, dict):
            attr_raw = raw_profile.get("parent_attribute")
            if isinstance(attr_raw, str) and attr_raw.strip() != "":
                cols.add(attr_raw.strip())

    for rules in compiled_timeline_constraints.values():
        for rule in rules:
            references = rule.get("references")
            if not isinstance(references, list):
                continue
            for raw_reference in references:
                if not isinstance(raw_reference, dict):
                    continue
                parent_table = str(raw_reference.get("parent_table", "")).strip()
                parent_column = str(raw_reference.get("parent_column", "")).strip()
                parent_pk_column = str(raw_reference.get("parent_pk_column", "")).strip()
                if parent_table == "":
                    continue
                cols = required_by_table.setdefault(parent_table, set())
                if parent_column != "":
                    cols.add(parent_column)
                if parent_pk_column != "":
                    cols.add(parent_pk_column)
    return required_by_table


def _cache_parent_rows(
    rows: list[dict[str, object]],
    *,
    required_columns: set[str],
) -> list[dict[str, object]]:
    if not required_columns:
        return rows
    cached_rows: list[dict[str, object]] = []
    for row in rows:
        cached_row: dict[str, object] = {}
        for column_name in required_columns:
            cached_row[column_name] = row.get(column_name)
        cached_rows.append(cached_row)
    return cached_rows


def _generate_project_rows_internal(
    project: SchemaProject,
    *,
    retain_rows: bool,
    on_table_rows: Callable[[str, list[dict[str, object]]], None] | None = None,
) -> dict[str, list[dict[str, object]]]:
    reset_runtime_generator_state()
    validate_project(project)
    effective_project = _resolve_sample_profile_fits(project)
    validate_project(effective_project)
    compiled_timeline_constraints = _compile_timeline_constraints(effective_project)
    compiled_data_quality_profiles = _compile_data_quality_profiles(effective_project)
    compiled_locale_identity_bundles = _compile_locale_identity_bundles(effective_project)
    locale_bundle_state: dict[str, dict[tuple[str, object], dict[str, object]]] = {}

    table_map: dict[str, TableSpec] = {t.table_name: t for t in effective_project.tables}

    fks_by_child: dict[str, list[ForeignKeySpec]] = {}
    for fk in effective_project.foreign_keys:
        fks_by_child.setdefault(fk.child_table, []).append(fk)

    parent_cache_columns = _compile_parent_cache_columns(
        effective_project,
        compiled_timeline_constraints=compiled_timeline_constraints,
    )
    remaining_parent_consumers: dict[str, int] = {table.table_name: 0 for table in effective_project.tables}
    for fk in effective_project.foreign_keys:
        remaining_parent_consumers[fk.parent_table] = remaining_parent_consumers.get(fk.parent_table, 0) + 1

    related_by_table = compiled_locale_identity_bundles.get("related_by_table")
    remaining_related_bundle_consumers: dict[str, int] = {}
    if isinstance(related_by_table, dict):
        for specs in related_by_table.values():
            if not isinstance(specs, list):
                continue
            for spec in specs:
                if not isinstance(spec, dict):
                    continue
                bundle_id = str(spec.get("bundle_id", "")).strip()
                if bundle_id == "":
                    continue
                remaining_related_bundle_consumers[bundle_id] = (
                    remaining_related_bundle_consumers.get(bundle_id, 0) + 1
                )

    order = _dependency_order(effective_project)
    parent_rows_by_table: dict[str, list[dict[str, object]]] = {}
    retained_rows_by_table: dict[str, list[dict[str, object]]] = {}

    def _assign_fk_column(
        rng: random.Random,
        rows: list[dict[str, object]],
        child_fk_col: str,
        parent_ids: list[int],
        min_children: int,
        max_children: int,
        *,
        child_table: str,
        parent_table: str,
        parent_weights: list[float] | None = None,
        extra_level_weights: list[float] | None = None,
    ) -> None:
        """
        Assign rows[*][child_fk_col] such that each parent_id appears between min_children and max_children times.

        This requires:
            len(parent_ids) * min_children <= len(rows) <= len(parent_ids) * max_children
        """
        location = f"Table '{child_table}', FK column '{child_fk_col}'"
        counts = _allocate_fk_child_counts(
            rng,
            parent_ids=parent_ids,
            min_children=min_children,
            max_children=max_children,
            total_children=len(rows),
            location=location,
            parent_weights=parent_weights,
            extra_level_weights=extra_level_weights,
        )

        # Build the pool
        pool: list[int] = []
        for pid, k in zip(parent_ids, counts, strict=True):
            pool.extend([pid] * k)

        rng.shuffle(pool)

        # Assign
        for r, pid in zip(rows, pool, strict=True):
            r[child_fk_col] = pid

    def _record_table_rows(
        table_name: str,
        rows: list[dict[str, object]],
    ) -> None:
        if retain_rows:
            retained_rows_by_table[table_name] = rows
        if on_table_rows is not None:
            on_table_rows(table_name, rows)

        if remaining_parent_consumers.get(table_name, 0) <= 0:
            parent_rows_by_table.pop(table_name, None)
            return

        required_columns = set(parent_cache_columns.get(table_name, set()))
        if not required_columns:
            parent_rows_by_table[table_name] = rows
            return
        parent_rows_by_table[table_name] = _cache_parent_rows(rows, required_columns=required_columns)

    def _release_parent_rows_for_consumed_fks(
        incoming_fks: list[ForeignKeySpec],
    ) -> None:
        for fk in incoming_fks:
            parent_name = fk.parent_table
            remaining = remaining_parent_consumers.get(parent_name, 0) - 1
            remaining_parent_consumers[parent_name] = max(0, remaining)
            if remaining_parent_consumers[parent_name] == 0:
                parent_rows_by_table.pop(parent_name, None)

    def _release_bundle_state_after_related_table(table_name: str) -> None:
        if not isinstance(related_by_table, dict):
            return
        related_specs = related_by_table.get(table_name, [])
        if isinstance(related_specs, list):
            for spec in related_specs:
                if not isinstance(spec, dict):
                    continue
                bundle_id = str(spec.get("bundle_id", "")).strip()
                if bundle_id == "":
                    continue
                remaining = remaining_related_bundle_consumers.get(bundle_id, 0) - 1
                remaining_related_bundle_consumers[bundle_id] = max(0, remaining)
        for bundle_id in list(locale_bundle_state.keys()):
            if remaining_related_bundle_consumers.get(bundle_id, 0) <= 0:
                locale_bundle_state.pop(bundle_id, None)

    for table_name in order:
        t = table_map[table_name]
        rng = random.Random(_stable_subseed(effective_project.seed, f"table:{table_name}"))

        pk_col = _table_pk_col_name(t)
        incoming_fks = fks_by_child.get(table_name, [])
        ordered_cols = _order_columns_by_dependencies(t.columns)

        # -------------------------
        # ROOT TABLE (no incoming FK)
        # -------------------------
        if not incoming_fks:
            n = t.row_count
            rows: list[dict[str, object]] = []

            for i in range(1, n + 1):
                row: dict[str, object] = {}
                for col in ordered_cols:
                    row[col.name] = _gen_value(col, rng, i, table_name, row)

                rows.append(row)

            _apply_table_correlation_groups(t, rows, project_seed=effective_project.seed)
            rows = _apply_business_key_and_scd(t, rows, rng, incoming_fks=incoming_fks)
            _enforce_table_timeline_constraints(
                t,
                rows,
                results=parent_rows_by_table,
                compiled_constraints=compiled_timeline_constraints,
            )
            _apply_table_locale_identity_bundles(
                t,
                rows,
                project_seed=effective_project.seed,
                compiled_bundles=compiled_locale_identity_bundles,
                bundle_state=locale_bundle_state,
            )
            _apply_table_data_quality_profiles(
                t,
                rows,
                project_seed=effective_project.seed,
                compiled_profiles=compiled_data_quality_profiles,
            )

            # Defensive: ensure PK exists
            for r in rows:
                if r.get(pk_col) is None:
                    raise ValueError(
                        _runtime_error(
                            f"Table '{table_name}', column '{pk_col}'",
                            "primary key generated as null",
                            "set PK column nullable=false and use deterministic PK generation",
                        )
                    )

            # Extra defensive fill (should not normally trigger)
            for i, r in enumerate(rows, start=1):
                if r.get(pk_col) is None:
                    r[pk_col] = i

            _record_table_rows(table_name, rows)
            _release_bundle_state_after_related_table(table_name)
            logger.info("Generated root table '%s' rows=%d", table_name, len(rows))
            continue

        # -----------------------------------------
        # CHILD TABLE with exactly ONE incoming FK
        # -----------------------------------------
        if len(incoming_fks) == 1:
            fk = incoming_fks[0]
            parent_table_name = fk.parent_table
            parent_rows, parent_ids = _fk_parent_rows_and_ids(
                fk,
                results=parent_rows_by_table,
                child_table=table_name,
            )
            parent_weights = _build_fk_parent_weights(
                fk,
                parent_rows=parent_rows,
                child_table=table_name,
            )
            distribution = _normalize_fk_child_count_distribution(
                fk,
                child_table=table_name,
            )
            fk_location = f"Table '{table_name}', FK column '{fk.child_column}'"
            extra_capacity = fk.max_children - fk.min_children
            extra_weights, extra_level_weights = _compile_fk_distribution_weights(
                distribution,
                extra_capacity=extra_capacity,
                location=fk_location,
            )

            rows: list[dict[str, object]] = []
            next_pk = 1

            if parent_weights is None:
                if distribution is None:
                    for pid in parent_ids:
                        k = rng.randint(fk.min_children, fk.max_children)
                        for _ in range(k):
                            row: dict[str, object] = {}
                            for col in ordered_cols:
                                if col.name == fk.child_column:
                                    row[col.name] = pid
                                else:
                                    row[col.name] = _gen_value(col, rng, next_pk, table_name, row)
                            rows.append(row)
                            next_pk += 1
                else:
                    extra_choices = list(range(extra_capacity + 1))
                    for pid in parent_ids:
                        if extra_capacity > 0 and extra_weights is not None:
                            extra = int(rng.choices(extra_choices, weights=extra_weights, k=1)[0])
                        else:
                            extra = 0
                        k = fk.min_children + extra
                        for _ in range(k):
                            row: dict[str, object] = {}
                            for col in ordered_cols:
                                if col.name == fk.child_column:
                                    row[col.name] = pid
                                else:
                                    row[col.name] = _gen_value(col, rng, next_pk, table_name, row)
                            rows.append(row)
                            next_pk += 1
            else:
                requested_extras = _sample_requested_fk_extras(
                    rng,
                    parent_count=len(parent_ids),
                    extra_capacity=extra_capacity,
                    extra_weights=extra_weights,
                )
                positive_extra_capacity = sum(
                    extra_capacity
                    for weight in parent_weights
                    if weight > 0
                )
                min_total = len(parent_ids) * fk.min_children
                total_children = min_total + min(requested_extras, positive_extra_capacity)
                counts = _allocate_fk_child_counts(
                    rng,
                    parent_ids=parent_ids,
                    min_children=fk.min_children,
                    max_children=fk.max_children,
                    total_children=total_children,
                    location=fk_location,
                    parent_weights=parent_weights,
                    extra_level_weights=extra_level_weights,
                )
                for pid, k in zip(parent_ids, counts, strict=True):
                    for _ in range(k):
                        row = {}
                        for col in ordered_cols:
                            if col.name == fk.child_column:
                                row[col.name] = pid
                            else:
                                row[col.name] = _gen_value(col, rng, next_pk, table_name, row)
                        rows.append(row)
                        next_pk += 1

            _apply_table_correlation_groups(t, rows, project_seed=effective_project.seed)
            rows = _apply_business_key_and_scd(t, rows, rng, incoming_fks=incoming_fks)
            _enforce_table_timeline_constraints(
                t,
                rows,
                results=parent_rows_by_table,
                compiled_constraints=compiled_timeline_constraints,
            )
            _apply_table_locale_identity_bundles(
                t,
                rows,
                project_seed=effective_project.seed,
                compiled_bundles=compiled_locale_identity_bundles,
                bundle_state=locale_bundle_state,
            )
            _apply_table_data_quality_profiles(
                t,
                rows,
                project_seed=effective_project.seed,
                compiled_profiles=compiled_data_quality_profiles,
            )
            _record_table_rows(table_name, rows)
            _release_parent_rows_for_consumed_fks(incoming_fks)
            _release_bundle_state_after_related_table(table_name)
            logger.info(
                "Generated child table '%s' rows=%d (parent=%s rows=%d, per-parent=%d..%d)",
                table_name, len(rows), parent_table_name, len(parent_ids), fk.min_children, fk.max_children
            )
            continue

        # -----------------------------------------
        # CHILD TABLE with MULTIPLE incoming FKs
        # Strategy: generate total rows = t.row_count, then assign each FK column.
        # -----------------------------------------
        # Compute allowed range intersection across all incoming FKs
        fk_parent_specs: list[tuple[ForeignKeySpec, list[dict[str, object]], list[int]]] = []
        mins = []
        maxs = []
        for fk in incoming_fks:
            parent_rows, parent_ids = _fk_parent_rows_and_ids(
                fk,
                results=parent_rows_by_table,
                child_table=table_name,
            )
            fk_parent_specs.append((fk, parent_rows, parent_ids))
            mins.append(len(parent_ids) * fk.min_children)
            maxs.append(len(parent_ids) * fk.max_children)

        min_allowed = max(mins)
        max_allowed = min(maxs)

        if max_allowed < min_allowed:
            raise ValueError(
                _runtime_error(
                    f"Table '{table_name}'",
                    f"FK constraints produce an empty row_count range (min_allowed={min_allowed}, max_allowed={max_allowed})",
                    "adjust FK min_children/max_children so ranges overlap",
                )
            )

        # If user set row_count > 0, use it; else auto-pick a value in the intersection
        if t.row_count and t.row_count > 0:
            n = t.row_count
            if not (min_allowed <= n <= max_allowed):
                raise ValueError(
                    _runtime_error(
                        f"Table '{table_name}'",
                        f"row_count={n} is outside FK-constrained range [{min_allowed}, {max_allowed}]",
                        "set row_count within the allowed range or adjust FK bounds",
                    )
                )
        else:
            n = rng.randint(min_allowed, max_allowed)


        fk_cols = {fk.child_column for fk in incoming_fks}

        rows: list[dict[str, object]] = []
        for i in range(1, n + 1):
            row: dict[str, object] = {}
            for col in ordered_cols:
                if col.name in fk_cols:
                    # placeholder; we'll assign after parents exist
                    row[col.name] = None
                else:
                    row[col.name] = _gen_value(col, rng, i, table_name, row)
            rows.append(row)

        # Defensive: ensure PK exists
        for r in rows:
            if r.get(pk_col) is None:
                raise ValueError(
                    _runtime_error(
                        f"Table '{table_name}', column '{pk_col}'",
                        "primary key generated as null",
                        "set PK column nullable=false and use deterministic PK generation",
                    )
                )

        # Assign each FK column independently, enforcing its min/max rules
        for fk, parent_rows, parent_ids in fk_parent_specs:
            parent_weights = _build_fk_parent_weights(
                fk,
                parent_rows=parent_rows,
                child_table=table_name,
            )
            distribution = _normalize_fk_child_count_distribution(
                fk,
                child_table=table_name,
            )
            _, extra_level_weights = _compile_fk_distribution_weights(
                distribution,
                extra_capacity=(fk.max_children - fk.min_children),
                location=f"Table '{table_name}', FK column '{fk.child_column}'",
            )
            # Use a stable subseed per FK so results are repeatable
            fk_rng = random.Random(
                _stable_subseed(
                    effective_project.seed,
                    f"fk:{table_name}:{fk.child_column}:{fk.parent_table}",
                )
            )

            _assign_fk_column(
                fk_rng,
                rows,
                fk.child_column,
                parent_ids,
                fk.min_children,
                fk.max_children,
                child_table=table_name,
                parent_table=fk.parent_table,
                parent_weights=parent_weights,
                extra_level_weights=extra_level_weights,
            )

        _apply_table_correlation_groups(t, rows, project_seed=effective_project.seed)
        rows = _apply_business_key_and_scd(t, rows, rng, incoming_fks=incoming_fks)
        _enforce_table_timeline_constraints(
            t,
            rows,
            results=parent_rows_by_table,
            compiled_constraints=compiled_timeline_constraints,
        )
        _apply_table_locale_identity_bundles(
            t,
            rows,
            project_seed=effective_project.seed,
            compiled_bundles=compiled_locale_identity_bundles,
            bundle_state=locale_bundle_state,
        )
        _apply_table_data_quality_profiles(
            t,
            rows,
            project_seed=effective_project.seed,
            compiled_profiles=compiled_data_quality_profiles,
        )
        _record_table_rows(table_name, rows)
        _release_parent_rows_for_consumed_fks(incoming_fks)
        _release_bundle_state_after_related_table(table_name)

        logger.info(
            "Generated multi-FK child table '%s' rows=%d (incoming_fks=%d)",
            table_name, len(rows), len(incoming_fks)
        )

    return retained_rows_by_table


logger = logging.getLogger("generator_project")

__all__ = ["_compile_parent_cache_columns", "_cache_parent_rows", "_generate_project_rows_internal"]
