from __future__ import annotations

from src.locale_identity import LOCALE_IDENTITY_PACKS
from src.locale_identity import SUPPORTED_LOCALE_IDENTITY_SLOTS
from src.schema.types import SchemaProject
from src.schema.types import TableSpec
from src.schema.validators.common import _parse_non_negative_finite_float
from src.schema.validators.common import _validation_error


def validate_locale_identity_bundles(project: SchemaProject, *, table_map: dict[str, TableSpec]) -> None:
    locale_identity_bundles = project.locale_identity_bundles
    if locale_identity_bundles is not None:
        if not isinstance(locale_identity_bundles, list):
            raise ValueError(
                _validation_error(
                    "Project",
                    "locale_identity_bundles must be a list when provided",
                    "set locale_identity_bundles to a list of DG09 bundle objects or omit locale_identity_bundles",
                )
            )
        if len(locale_identity_bundles) == 0:
            raise ValueError(
                _validation_error(
                    "Project",
                    "locale_identity_bundles cannot be empty when provided",
                    "add one or more DG09 bundle objects or omit locale_identity_bundles",
                )
            )

        allowed_slots = set(SUPPORTED_LOCALE_IDENTITY_SLOTS)
        supported_locales = set(LOCALE_IDENTITY_PACKS.keys())
        seen_bundle_ids: set[str] = set()
        for bundle_index, raw_bundle in enumerate(locale_identity_bundles):
            location = f"Project locale_identity_bundles[{bundle_index}]"
            if not isinstance(raw_bundle, dict):
                raise ValueError(
                    _validation_error(
                        location,
                        "bundle must be a JSON object",
                        "configure this DG09 bundle as an object with bundle_id, base_table, and columns",
                    )
                )

            bundle_id_raw = raw_bundle.get("bundle_id")
            if not isinstance(bundle_id_raw, str) or bundle_id_raw.strip() == "":
                raise ValueError(
                    _validation_error(
                        location,
                        "bundle_id is required",
                        "set bundle_id to a non-empty string",
                    )
                )
            bundle_id = bundle_id_raw.strip()
            if bundle_id in seen_bundle_ids:
                raise ValueError(
                    _validation_error(
                        "Project",
                        f"duplicate DG09 bundle_id '{bundle_id}'",
                        "use unique bundle_id values in locale_identity_bundles",
                    )
                )
            seen_bundle_ids.add(bundle_id)

            base_table_raw = raw_bundle.get("base_table")
            if not isinstance(base_table_raw, str) or base_table_raw.strip() == "":
                raise ValueError(
                    _validation_error(
                        location,
                        "base_table is required",
                        "set base_table to an existing table name",
                    )
                )
            base_table_name = base_table_raw.strip()
            base_table = table_map.get(base_table_name)
            if base_table is None:
                raise ValueError(
                    _validation_error(
                        location,
                        f"base_table '{base_table_name}' was not found",
                        "use an existing table name for base_table",
                    )
                )
            base_cols = {column.name: column for column in base_table.columns}

            columns_raw = raw_bundle.get("columns")
            if not isinstance(columns_raw, dict) or len(columns_raw) == 0:
                raise ValueError(
                    _validation_error(
                        location,
                        "columns must be a non-empty object",
                        "set columns to a mapping like {'first_name': 'first_name_col', 'postcode': 'postcode_col'}",
                    )
                )
            seen_slots: set[str] = set()
            for raw_slot, raw_column in columns_raw.items():
                if not isinstance(raw_slot, str) or raw_slot.strip() == "":
                    raise ValueError(
                        _validation_error(
                            location,
                            "columns contains an empty or non-string slot key",
                            f"use one or more supported slots: {', '.join(sorted(allowed_slots))}",
                        )
                    )
                slot = raw_slot.strip()
                if slot not in allowed_slots:
                    raise ValueError(
                        _validation_error(
                            location,
                            f"unsupported columns slot '{raw_slot}'",
                            f"use one of: {', '.join(sorted(allowed_slots))}",
                        )
                    )
                if slot in seen_slots:
                    raise ValueError(
                        _validation_error(
                            location,
                            f"columns has duplicate slot '{slot}' after normalization",
                            "list each DG09 slot once in columns",
                        )
                    )
                seen_slots.add(slot)

                if not isinstance(raw_column, str) or raw_column.strip() == "":
                    raise ValueError(
                        _validation_error(
                            location,
                            f"columns['{raw_slot}'] must be a non-empty string column name",
                            "map each slot to an existing table column name",
                        )
                    )
                column_name = raw_column.strip()
                column = base_cols.get(column_name)
                if column is None:
                    raise ValueError(
                        _validation_error(
                            location,
                            f"columns['{raw_slot}'] column '{column_name}' was not found on table '{base_table_name}'",
                            "map DG09 slots to existing base_table columns",
                        )
                    )
                if column.primary_key:
                    raise ValueError(
                        _validation_error(
                            location,
                            f"columns['{raw_slot}'] cannot target primary key column '{column_name}'",
                            "target non-primary-key columns for locale identity bundle values",
                        )
                    )

            locale_raw = raw_bundle.get("locale")
            locale_weights_raw = raw_bundle.get("locale_weights")
            if locale_raw is not None and locale_weights_raw is not None:
                raise ValueError(
                    _validation_error(
                        location,
                        "locale and locale_weights cannot both be set",
                        "set exactly one of locale or locale_weights, or omit both to use default locale",
                    )
                )
            if locale_raw is not None:
                if not isinstance(locale_raw, str) or locale_raw.strip() == "":
                    raise ValueError(
                        _validation_error(
                            location,
                            "locale must be a non-empty string when provided",
                            f"use one of: {', '.join(sorted(supported_locales))}",
                        )
                    )
                locale_name = locale_raw.strip()
                if locale_name not in supported_locales:
                    raise ValueError(
                        _validation_error(
                            location,
                            f"unsupported locale '{locale_raw}'",
                            f"use one of: {', '.join(sorted(supported_locales))}",
                        )
                    )
            if locale_weights_raw is not None:
                if not isinstance(locale_weights_raw, dict) or len(locale_weights_raw) == 0:
                    raise ValueError(
                        _validation_error(
                            location,
                            "locale_weights must be a non-empty object when provided",
                            "set locale_weights to a mapping of locale ids to non-negative numeric weights",
                        )
                    )
                has_positive_weight = False
                for raw_locale, raw_weight in locale_weights_raw.items():
                    if not isinstance(raw_locale, str) or raw_locale.strip() == "":
                        raise ValueError(
                            _validation_error(
                                location,
                                "locale_weights contains an empty or non-string locale key",
                                f"use supported locale ids as keys: {', '.join(sorted(supported_locales))}",
                            )
                        )
                    locale_name = raw_locale.strip()
                    if locale_name not in supported_locales:
                        raise ValueError(
                            _validation_error(
                                location,
                                f"unsupported locale_weights key '{raw_locale}'",
                                f"use one of: {', '.join(sorted(supported_locales))}",
                            )
                        )
                    weight = _parse_non_negative_finite_float(
                        raw_weight,
                        location=location,
                        field_name=f"locale_weights['{raw_locale}']",
                        hint="use non-negative finite numeric weights",
                    )
                    if weight > 0.0:
                        has_positive_weight = True
                if not has_positive_weight:
                    raise ValueError(
                        _validation_error(
                            location,
                            "locale_weights provides no positive weight",
                            "set at least one locale weight > 0",
                        )
                    )

            related_tables_raw = raw_bundle.get("related_tables")
            if related_tables_raw is not None:
                if not isinstance(related_tables_raw, list):
                    raise ValueError(
                        _validation_error(
                            location,
                            "related_tables must be a list when provided",
                            "set related_tables to a list of objects with table, via_fk, and columns",
                        )
                    )
                for related_index, raw_related in enumerate(related_tables_raw):
                    related_location = f"{location}, related_tables[{related_index}]"
                    if not isinstance(raw_related, dict):
                        raise ValueError(
                            _validation_error(
                                related_location,
                                "related table entry must be a JSON object",
                                "configure table, via_fk, and columns for each related table",
                            )
                        )
                    related_table_raw = raw_related.get("table")
                    if not isinstance(related_table_raw, str) or related_table_raw.strip() == "":
                        raise ValueError(
                            _validation_error(
                                related_location,
                                "table is required",
                                "set table to an existing child table name",
                            )
                        )
                    related_table_name = related_table_raw.strip()
                    related_table = table_map.get(related_table_name)
                    if related_table is None:
                        raise ValueError(
                            _validation_error(
                                related_location,
                                f"table '{related_table_name}' was not found",
                                "use an existing related table name",
                            )
                        )
                    related_cols = {column.name: column for column in related_table.columns}

                    via_fk_raw = raw_related.get("via_fk")
                    if not isinstance(via_fk_raw, str) or via_fk_raw.strip() == "":
                        raise ValueError(
                            _validation_error(
                                related_location,
                                "via_fk is required",
                                "set via_fk to the FK child column linking related table rows to base_table",
                            )
                        )
                    via_fk = via_fk_raw.strip()
                    if via_fk not in related_cols:
                        raise ValueError(
                            _validation_error(
                                related_location,
                                f"via_fk '{via_fk}' was not found on table '{related_table_name}'",
                                "use an existing related table column for via_fk",
                            )
                        )
                    direct_fk = next(
                        (
                            fk
                            for fk in project.foreign_keys
                            if fk.child_table == related_table_name
                            and fk.child_column == via_fk
                            and fk.parent_table == base_table_name
                        ),
                        None,
                    )
                    if direct_fk is None:
                        raise ValueError(
                            _validation_error(
                                related_location,
                                (
                                    f"via_fk '{related_table_name}.{via_fk}' does not directly reference "
                                    f"base_table '{base_table_name}'"
                                ),
                                "define a direct FK from related table via_fk to base_table before using this DG09 mapping",
                            )
                        )

                    related_columns_raw = raw_related.get("columns")
                    if not isinstance(related_columns_raw, dict) or len(related_columns_raw) == 0:
                        raise ValueError(
                            _validation_error(
                                related_location,
                                "columns must be a non-empty object",
                                "set columns to a mapping like {'currency_code': 'currency_code_col'}",
                            )
                        )
                    seen_related_slots: set[str] = set()
                    for raw_slot, raw_column in related_columns_raw.items():
                        if not isinstance(raw_slot, str) or raw_slot.strip() == "":
                            raise ValueError(
                                _validation_error(
                                    related_location,
                                    "columns contains an empty or non-string slot key",
                                    f"use one or more supported slots: {', '.join(sorted(allowed_slots))}",
                                )
                            )
                        slot = raw_slot.strip()
                        if slot not in allowed_slots:
                            raise ValueError(
                                _validation_error(
                                    related_location,
                                    f"unsupported columns slot '{raw_slot}'",
                                    f"use one of: {', '.join(sorted(allowed_slots))}",
                                )
                            )
                        if slot in seen_related_slots:
                            raise ValueError(
                                _validation_error(
                                    related_location,
                                    f"columns has duplicate slot '{slot}' after normalization",
                                    "list each DG09 slot once in related table columns mapping",
                                )
                            )
                        seen_related_slots.add(slot)

                        if not isinstance(raw_column, str) or raw_column.strip() == "":
                            raise ValueError(
                                _validation_error(
                                    related_location,
                                    f"columns['{raw_slot}'] must be a non-empty string column name",
                                    "map each slot to an existing related table column name",
                                )
                            )
                        column_name = raw_column.strip()
                        column = related_cols.get(column_name)
                        if column is None:
                            raise ValueError(
                                _validation_error(
                                    related_location,
                                    (
                                        f"columns['{raw_slot}'] column '{column_name}' was not found "
                                        f"on table '{related_table_name}'"
                                    ),
                                    "map DG09 slots to existing related table columns",
                                )
                            )
                        if column.primary_key:
                            raise ValueError(
                                _validation_error(
                                    related_location,
                                    f"columns['{raw_slot}'] cannot target primary key column '{column_name}'",
                                    "target non-primary-key columns for related-table locale bundle values",
                                )
                            )



__all__ = ["validate_locale_identity_bundles"]
