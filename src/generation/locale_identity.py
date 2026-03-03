"""Locale-identity bundle (DG09) helpers."""

from __future__ import annotations

import math
import random

from src.generation.common import _runtime_error, _stable_subseed
from src.generation.fk_assignment import _fk_lookup_identity
from src.generation.scd import _table_pk_col_name
from src.locale_identity import LOCALE_IDENTITY_PACKS, SUPPORTED_LOCALE_IDENTITY_SLOTS
from src.schema_project_model import SchemaProject, TableSpec

def _normalize_locale_identity_columns(
    raw_columns: object,
    *,
    location: str,
    table_name: str,
    table_columns: dict[str, ColumnSpec],
) -> dict[str, str]:
    if not isinstance(raw_columns, dict) or len(raw_columns) == 0:
        raise ValueError(
            _runtime_error(
                location,
                "columns must be a non-empty object",
                "set columns to a mapping of DG09 slots to existing table columns",
            )
        )

    allowed_slots = set(SUPPORTED_LOCALE_IDENTITY_SLOTS)
    normalized: dict[str, str] = {}
    for raw_slot, raw_column in raw_columns.items():
        if not isinstance(raw_slot, str) or raw_slot.strip() == "":
            raise ValueError(
                _runtime_error(
                    location,
                    "columns contains an empty or non-string slot key",
                    f"use one or more supported slots: {', '.join(sorted(allowed_slots))}",
                )
            )
        slot = raw_slot.strip()
        if slot not in allowed_slots:
            raise ValueError(
                _runtime_error(
                    location,
                    f"unsupported columns slot '{raw_slot}'",
                    f"use one of: {', '.join(sorted(allowed_slots))}",
                )
            )
        if slot in normalized:
            raise ValueError(
                _runtime_error(
                    location,
                    f"columns has duplicate slot '{slot}' after normalization",
                    "list each DG09 slot once",
                )
            )
        if not isinstance(raw_column, str) or raw_column.strip() == "":
            raise ValueError(
                _runtime_error(
                    location,
                    f"columns['{raw_slot}'] must be a non-empty string column name",
                    "map each slot to an existing table column",
                )
            )
        column_name = raw_column.strip()
        column = table_columns.get(column_name)
        if column is None:
            raise ValueError(
                _runtime_error(
                    location,
                    f"columns['{raw_slot}'] column '{column_name}' was not found on table '{table_name}'",
                    "map each slot to an existing column on the configured table",
                )
            )
        if column.primary_key:
            raise ValueError(
                _runtime_error(
                    location,
                    f"columns['{raw_slot}'] cannot target primary key column '{column_name}'",
                    "target non-primary-key columns for DG09 locale identity fields",
                )
            )
        normalized[slot] = column_name
    return normalized


def _compile_locale_selector(
    raw_bundle: dict[str, object],
    *,
    location: str,
) -> tuple[list[str], list[float]]:
    locale_raw = raw_bundle.get("locale")
    locale_weights_raw = raw_bundle.get("locale_weights")
    supported_locales = set(LOCALE_IDENTITY_PACKS.keys())

    if locale_raw is not None and locale_weights_raw is not None:
        raise ValueError(
            _runtime_error(
                location,
                "locale and locale_weights cannot both be set",
                "set exactly one of locale or locale_weights, or omit both to use default locale",
            )
        )
    if locale_raw is not None:
        if not isinstance(locale_raw, str) or locale_raw.strip() == "":
            raise ValueError(
                _runtime_error(
                    location,
                    "locale must be a non-empty string when provided",
                    f"use one of: {', '.join(sorted(supported_locales))}",
                )
            )
        locale_name = locale_raw.strip()
        if locale_name not in supported_locales:
            raise ValueError(
                _runtime_error(
                    location,
                    f"unsupported locale '{locale_raw}'",
                    f"use one of: {', '.join(sorted(supported_locales))}",
                )
            )
        return [locale_name], [1.0]

    if locale_weights_raw is None:
        return ["en-US"], [1.0]

    if not isinstance(locale_weights_raw, dict) or len(locale_weights_raw) == 0:
        raise ValueError(
            _runtime_error(
                location,
                "locale_weights must be a non-empty object when provided",
                "set locale_weights to a mapping of locale ids to non-negative numeric weights",
            )
        )

    locales: list[str] = []
    weights: list[float] = []
    has_positive_weight = False
    for raw_locale, raw_weight in locale_weights_raw.items():
        if not isinstance(raw_locale, str) or raw_locale.strip() == "":
            raise ValueError(
                _runtime_error(
                    location,
                    "locale_weights contains an empty or non-string locale key",
                    f"use supported locale ids as keys: {', '.join(sorted(supported_locales))}",
                )
            )
        locale_name = raw_locale.strip()
        if locale_name not in supported_locales:
            raise ValueError(
                _runtime_error(
                    location,
                    f"unsupported locale_weights key '{raw_locale}'",
                    f"use one of: {', '.join(sorted(supported_locales))}",
                )
            )
        try:
            weight = float(raw_weight)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                _runtime_error(
                    location,
                    f"locale_weights['{raw_locale}'] must be numeric",
                    "use non-negative finite numeric weights",
                )
            ) from exc
        if (not math.isfinite(weight)) or weight < 0.0:
            raise ValueError(
                _runtime_error(
                    location,
                    f"locale_weights['{raw_locale}'] must be a finite value >= 0",
                    "use non-negative finite numeric weights",
                )
            )
        if weight > 0.0:
            has_positive_weight = True
        locales.append(locale_name)
        weights.append(weight)

    if not has_positive_weight:
        raise ValueError(
            _runtime_error(
                location,
                "locale_weights provides no positive weight",
                "set at least one locale weight > 0",
            )
        )
    return locales, weights


def _compile_locale_identity_bundles(project: SchemaProject) -> dict[str, dict[str, list[dict[str, object]]]]:
    raw_bundles = project.locale_identity_bundles
    if not raw_bundles:
        return {"base_by_table": {}, "related_by_table": {}}

    table_map = {table.table_name: table for table in project.tables}
    base_by_table: dict[str, list[dict[str, object]]] = {}
    related_by_table: dict[str, list[dict[str, object]]] = {}

    for bundle_index, raw_bundle in enumerate(raw_bundles):
        location = f"Project locale_identity_bundles[{bundle_index}]"
        if not isinstance(raw_bundle, dict):
            raise ValueError(
                _runtime_error(
                    location,
                    "bundle must be an object",
                    "set each locale_identity_bundles item to a JSON object",
                )
            )

        bundle_id_raw = raw_bundle.get("bundle_id")
        if not isinstance(bundle_id_raw, str) or bundle_id_raw.strip() == "":
            raise ValueError(
                _runtime_error(
                    location,
                    "bundle_id is required",
                    "set bundle_id to a non-empty string",
                )
            )
        bundle_id = bundle_id_raw.strip()

        base_table_raw = raw_bundle.get("base_table")
        if not isinstance(base_table_raw, str) or base_table_raw.strip() == "":
            raise ValueError(
                _runtime_error(
                    location,
                    "base_table is required",
                    "set base_table to an existing table name",
                )
            )
        base_table_name = base_table_raw.strip()
        base_table = table_map.get(base_table_name)
        if base_table is None:
            raise ValueError(
                _runtime_error(
                    location,
                    f"base_table '{base_table_name}' was not found",
                    "use an existing table name for base_table",
                )
            )
        base_columns = {column.name: column for column in base_table.columns}
        base_column_map = _normalize_locale_identity_columns(
            raw_bundle.get("columns"),
            location=location,
            table_name=base_table_name,
            table_columns=base_columns,
        )
        locale_ids, locale_weights = _compile_locale_selector(raw_bundle, location=location)

        base_by_table.setdefault(base_table_name, []).append(
            {
                "bundle_id": bundle_id,
                "bundle_index": bundle_index,
                "table": base_table_name,
                "pk_column": _table_pk_col_name(base_table),
                "columns": base_column_map,
                "locale_ids": locale_ids,
                "locale_weights": locale_weights,
            }
        )

        related_tables_raw = raw_bundle.get("related_tables")
        if related_tables_raw is None:
            continue
        if not isinstance(related_tables_raw, list):
            raise ValueError(
                _runtime_error(
                    location,
                    "related_tables must be a list when provided",
                    "set related_tables to a list of objects with table, via_fk, and columns",
                )
            )
        for related_index, raw_related in enumerate(related_tables_raw):
            related_location = f"{location}, related_tables[{related_index}]"
            if not isinstance(raw_related, dict):
                raise ValueError(
                    _runtime_error(
                        related_location,
                        "related table entry must be an object",
                        "configure table, via_fk, and columns for each related table object",
                    )
                )
            related_table_raw = raw_related.get("table")
            if not isinstance(related_table_raw, str) or related_table_raw.strip() == "":
                raise ValueError(
                    _runtime_error(
                        related_location,
                        "table is required",
                        "set table to an existing related table name",
                    )
                )
            related_table_name = related_table_raw.strip()
            related_table = table_map.get(related_table_name)
            if related_table is None:
                raise ValueError(
                    _runtime_error(
                        related_location,
                        f"table '{related_table_name}' was not found",
                        "use an existing related table name",
                    )
                )
            related_columns = {column.name: column for column in related_table.columns}

            via_fk_raw = raw_related.get("via_fk")
            if not isinstance(via_fk_raw, str) or via_fk_raw.strip() == "":
                raise ValueError(
                    _runtime_error(
                        related_location,
                        "via_fk is required",
                        "set via_fk to the related-table FK child column that references base_table",
                    )
                )
            via_fk = via_fk_raw.strip()
            if via_fk not in related_columns:
                raise ValueError(
                    _runtime_error(
                        related_location,
                        f"via_fk '{via_fk}' was not found on table '{related_table_name}'",
                        "use an existing related-table column for via_fk",
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
                    _runtime_error(
                        related_location,
                        (
                            f"via_fk '{related_table_name}.{via_fk}' does not directly reference "
                            f"base_table '{base_table_name}'"
                        ),
                        "define a direct FK from related table via_fk to base_table before using this DG09 mapping",
                    )
                )

            related_column_map = _normalize_locale_identity_columns(
                raw_related.get("columns"),
                location=related_location,
                table_name=related_table_name,
                table_columns=related_columns,
            )
            related_by_table.setdefault(related_table_name, []).append(
                {
                    "bundle_id": bundle_id,
                    "bundle_index": bundle_index,
                    "related_index": related_index,
                    "base_table": base_table_name,
                    "table": related_table_name,
                    "via_fk": via_fk,
                    "columns": related_column_map,
                }
            )

    return {"base_by_table": base_by_table, "related_by_table": related_by_table}


def _format_locale_phone(
    *,
    locale_id: str,
    city_profile: dict[str, object],
    rng: random.Random,
) -> tuple[str, str]:
    raw_area_codes = city_profile.get("area_codes")
    area_codes = (
        [str(value).strip() for value in raw_area_codes if str(value).strip() != ""]
        if isinstance(raw_area_codes, list)
        else []
    )

    if locale_id == "en-US":
        area = rng.choice(area_codes) if area_codes else str(rng.randint(201, 989))
        prefix = rng.randint(200, 999)
        line = rng.randint(1000, 9999)
        national = f"({area}) {prefix:03d}-{line:04d}"
        e164 = f"+1{area}{prefix:03d}{line:04d}"
        return national, e164

    if locale_id == "en-GB":
        area = rng.choice(area_codes) if area_codes else "20"
        part_a = rng.randint(1000, 9999)
        part_b = rng.randint(1000, 9999)
        national = f"0{area} {part_a:04d} {part_b:04d}"
        e164 = f"+44{area}{part_a:04d}{part_b:04d}"
        return national, e164

    if locale_id == "fr-FR":
        area = rng.choice(area_codes) if area_codes else "1"
        groups = [rng.randint(0, 99) for _ in range(4)]
        tail = "".join(f"{group:02d}" for group in groups)
        national = f"0{area} " + " ".join(f"{group:02d}" for group in groups)
        e164 = f"+33{area}{tail}"
        return national, e164

    area = rng.choice(area_codes) if area_codes else "30"
    part_a = rng.randint(100, 999)
    part_b = rng.randint(1000, 9999)
    national = f"0{area} {part_a:03d} {part_b:04d}"
    e164 = f"+49{area}{part_a:03d}{part_b:04d}"
    return national, e164


def _build_locale_identity_payload(
    *,
    locale_id: str,
    rng: random.Random,
) -> dict[str, object]:
    pack = LOCALE_IDENTITY_PACKS.get(locale_id)
    if pack is None:
        raise ValueError(
            _runtime_error(
                "DG09 locale payload builder",
                f"unsupported locale '{locale_id}'",
                f"use one of: {', '.join(sorted(LOCALE_IDENTITY_PACKS.keys()))}",
            )
        )

    first_names_raw = pack.get("first_names")
    last_names_raw = pack.get("last_names")
    streets_raw = pack.get("streets")
    cities_raw = pack.get("cities")
    if not isinstance(first_names_raw, list) or not first_names_raw:
        raise ValueError(
            _runtime_error(
                "DG09 locale payload builder",
                f"locale pack '{locale_id}' has no first_names",
                "provide one or more first_names in the locale pack",
            )
        )
    if not isinstance(last_names_raw, list) or not last_names_raw:
        raise ValueError(
            _runtime_error(
                "DG09 locale payload builder",
                f"locale pack '{locale_id}' has no last_names",
                "provide one or more last_names in the locale pack",
            )
        )
    if not isinstance(streets_raw, list) or not streets_raw:
        raise ValueError(
            _runtime_error(
                "DG09 locale payload builder",
                f"locale pack '{locale_id}' has no streets",
                "provide one or more streets in the locale pack",
            )
        )
    if not isinstance(cities_raw, list) or not cities_raw:
        raise ValueError(
            _runtime_error(
                "DG09 locale payload builder",
                f"locale pack '{locale_id}' has no cities",
                "provide one or more city profiles in the locale pack",
            )
        )

    first_name = str(rng.choice(first_names_raw))
    last_name = str(rng.choice(last_names_raw))
    street = str(rng.choice(streets_raw))
    city_profile_raw = rng.choice(cities_raw)
    if not isinstance(city_profile_raw, dict):
        raise ValueError(
            _runtime_error(
                "DG09 locale payload builder",
                f"locale pack '{locale_id}' city profile must be an object",
                "fix locale pack city entries so each value is an object",
            )
        )
    city_profile = city_profile_raw

    city_name = str(city_profile.get("city", "")).strip()
    region = str(city_profile.get("region", "")).strip()
    if city_name == "" or region == "":
        raise ValueError(
            _runtime_error(
                "DG09 locale payload builder",
                f"locale pack '{locale_id}' city profile requires city and region",
                "set city and region for each locale city profile",
            )
        )

    postcodes_raw = city_profile.get("postcodes")
    if not isinstance(postcodes_raw, list) or not postcodes_raw:
        raise ValueError(
            _runtime_error(
                "DG09 locale payload builder",
                f"locale pack '{locale_id}' city profile has no postcodes",
                "set one or more postcode values in each city profile",
            )
        )
    postcode = str(rng.choice(postcodes_raw)).strip()
    if postcode == "":
        raise ValueError(
            _runtime_error(
                "DG09 locale payload builder",
                f"locale pack '{locale_id}' produced an empty postcode value",
                "use non-empty postcode values in locale packs",
            )
        )

    national_phone, phone_e164 = _format_locale_phone(locale_id=locale_id, city_profile=city_profile, rng=rng)
    house_number = rng.randint(1, 9999)
    full_name = f"{first_name} {last_name}"
    return {
        "locale": locale_id,
        "country_code": str(pack.get("country_code", "")).strip(),
        "currency_code": str(pack.get("currency_code", "")).strip(),
        "currency_symbol": str(pack.get("currency_symbol", "")).strip(),
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full_name,
        "address_line1": f"{house_number} {street}",
        "city": city_name,
        "region": region,
        "postcode": postcode,
        "phone_e164": phone_e164,
        "phone_national": national_phone,
    }


def _apply_table_locale_identity_bundles(
    table: TableSpec,
    rows: list[dict[str, object]],
    *,
    project_seed: int,
    compiled_bundles: dict[str, dict[str, list[dict[str, object]]]],
    bundle_state: dict[str, dict[tuple[str, object], dict[str, object]]],
) -> None:
    if not rows:
        return
    base_by_table = compiled_bundles.get("base_by_table")
    related_by_table = compiled_bundles.get("related_by_table")
    if not isinstance(base_by_table, dict) or not isinstance(related_by_table, dict):
        return

    base_specs = base_by_table.get(table.table_name, [])
    for spec in base_specs:
        bundle_id = str(spec.get("bundle_id", "")).strip()
        bundle_index = int(spec.get("bundle_index", 0))
        pk_column = str(spec.get("pk_column", "")).strip()
        column_map = spec.get("columns")
        locale_ids_raw = spec.get("locale_ids")
        locale_weights_raw = spec.get("locale_weights")
        if bundle_id == "" or pk_column == "":
            continue
        if not isinstance(column_map, dict):
            continue
        if not isinstance(locale_ids_raw, list) or not locale_ids_raw:
            continue
        if not isinstance(locale_weights_raw, list) or len(locale_weights_raw) != len(locale_ids_raw):
            continue
        locale_ids = [str(locale).strip() for locale in locale_ids_raw if str(locale).strip() != ""]
        if not locale_ids:
            continue
        locale_weights = [float(weight) for weight in locale_weights_raw]

        bundle_rng = random.Random(
            _stable_subseed(project_seed, f"dg09:{table.table_name}:{bundle_id}:{bundle_index}")
        )
        values_by_key = bundle_state.setdefault(bundle_id, {})

        for row_index, row in enumerate(rows, start=1):
            key = _fk_lookup_identity(row.get(pk_column))
            if key[0] == "none":
                raise ValueError(
                    _runtime_error(
                        f"Table '{table.table_name}', row {row_index}, column '{pk_column}'",
                        "DG09 base key resolved to null",
                        "ensure the base table primary key column is populated before locale bundle application",
                    )
                )

            payload = values_by_key.get(key)
            if payload is None:
                locale_id = str(bundle_rng.choices(locale_ids, weights=locale_weights, k=1)[0])
                payload = _build_locale_identity_payload(locale_id=locale_id, rng=bundle_rng)
                values_by_key[key] = payload

            for slot, column_name_raw in column_map.items():
                column_name = str(column_name_raw).strip()
                if column_name == "":
                    continue
                row[column_name] = payload.get(slot)

    related_specs = related_by_table.get(table.table_name, [])
    for spec in related_specs:
        bundle_id = str(spec.get("bundle_id", "")).strip()
        via_fk = str(spec.get("via_fk", "")).strip()
        column_map = spec.get("columns")
        if bundle_id == "" or via_fk == "":
            continue
        if not isinstance(column_map, dict):
            continue
        values_by_key = bundle_state.get(bundle_id)
        if not values_by_key:
            raise ValueError(
                _runtime_error(
                    f"Table '{table.table_name}'",
                    f"DG09 bundle '{bundle_id}' has no resolved base-table payloads",
                    "generate base table rows before related-table DG09 projections",
                )
            )
        for row_index, row in enumerate(rows, start=1):
            key = _fk_lookup_identity(row.get(via_fk))
            if key[0] == "none":
                continue
            payload = values_by_key.get(key)
            if payload is None:
                raise ValueError(
                    _runtime_error(
                        f"Table '{table.table_name}', row {row_index}, FK column '{via_fk}'",
                        f"DG09 could not find a base bundle payload for value {row.get(via_fk)!r}",
                        "ensure via_fk references an existing base-table key populated by the DG09 bundle",
                    )
                )
            for slot, column_name_raw in column_map.items():
                column_name = str(column_name_raw).strip()
                if column_name == "":
                    continue
                row[column_name] = payload.get(slot)


__all__ = ["_normalize_locale_identity_columns", "_compile_locale_selector", "_compile_locale_identity_bundles", "_format_locale_phone", "_build_locale_identity_payload", "_apply_table_locale_identity_bundles"]
