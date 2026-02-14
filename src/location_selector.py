from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Any

EARTH_RADIUS_KM = 6371.0088


def _location_error(field: str, issue: str, hint: str) -> str:
    return f"Location Selector / {field}: {issue}. Fix: {hint}."


def _parse_finite_float(value: Any, *, field: str, hint: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(_location_error(field, "must be numeric", hint)) from exc
    if not math.isfinite(out):
        raise ValueError(_location_error(field, "must be finite", hint))
    return out


def parse_latitude(value: Any) -> float:
    lat = _parse_finite_float(
        value,
        field="Latitude",
        hint="enter a numeric latitude between -90 and 90",
    )
    if lat < -90.0 or lat > 90.0:
        raise ValueError(
            _location_error(
                "Latitude",
                f"value {lat} is outside [-90, 90]",
                "enter a latitude between -90 and 90",
            )
        )
    return lat


def parse_longitude(value: Any) -> float:
    lon = _parse_finite_float(
        value,
        field="Longitude",
        hint="enter a numeric longitude between -180 and 180",
    )
    if lon < -180.0 or lon > 180.0:
        raise ValueError(
            _location_error(
                "Longitude",
                f"value {lon} is outside [-180, 180]",
                "enter a longitude between -180 and 180",
            )
        )
    return lon


def parse_radius_km(value: Any) -> float:
    radius = _parse_finite_float(
        value,
        field="Radius (km)",
        hint="enter a positive radius in kilometers",
    )
    if radius <= 0.0:
        raise ValueError(
            _location_error(
                "Radius (km)",
                f"value {radius} must be > 0",
                "enter a positive radius in kilometers",
            )
        )
    if radius > 20_000.0:
        raise ValueError(
            _location_error(
                "Radius (km)",
                f"value {radius} is too large for Earth-scale circle generation",
                "use a radius <= 20000 km",
            )
        )
    return radius


def parse_geojson_steps(value: Any) -> int:
    try:
        steps = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _location_error(
                "GeoJSON resolution",
                "must be an integer",
                "enter an integer value (12 or greater)",
            )
        ) from exc
    if steps < 12:
        raise ValueError(
            _location_error(
                "GeoJSON resolution",
                f"value {steps} must be >= 12",
                "enter a value of 12 or greater",
            )
        )
    if steps > 1440:
        raise ValueError(
            _location_error(
                "GeoJSON resolution",
                f"value {steps} is too large",
                "enter a value no greater than 1440",
            )
        )
    return steps


def parse_sample_count(value: Any) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _location_error(
                "Sample count",
                "must be an integer",
                "enter a positive whole number",
            )
        ) from exc
    if count <= 0:
        raise ValueError(
            _location_error(
                "Sample count",
                f"value {count} must be > 0",
                "enter a positive whole number",
            )
        )
    if count > 10000:
        raise ValueError(
            _location_error(
                "Sample count",
                f"value {count} is too large",
                "use a sample count <= 10000",
            )
        )
    return count


def parse_seed(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _location_error(
                "Seed",
                "must be an integer",
                "enter a whole-number seed",
            )
        ) from exc


def normalize_longitude(longitude: float) -> float:
    out = ((longitude + 180.0) % 360.0) - 180.0
    if out == -180.0 and longitude > 0:
        return 180.0
    return out


def destination_point(
    center_lat: float,
    center_lon: float,
    bearing_deg: float,
    distance_km: float,
) -> tuple[float, float]:
    lat1 = math.radians(center_lat)
    lon1 = math.radians(center_lon)
    angular = distance_km / EARTH_RADIUS_KM
    bearing = math.radians(bearing_deg)

    sin_lat1 = math.sin(lat1)
    cos_lat1 = math.cos(lat1)
    sin_ang = math.sin(angular)
    cos_ang = math.cos(angular)

    lat2 = math.asin(sin_lat1 * cos_ang + cos_lat1 * sin_ang * math.cos(bearing))
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * sin_ang * cos_lat1,
        cos_ang - sin_lat1 * math.sin(lat2),
    )
    return math.degrees(lat2), normalize_longitude(math.degrees(lon2))


def build_circle_ring(
    center_lat: Any,
    center_lon: Any,
    radius_km: Any,
    *,
    steps: Any = 72,
) -> list[list[float]]:
    lat = parse_latitude(center_lat)
    lon = parse_longitude(center_lon)
    radius = parse_radius_km(radius_km)
    step_count = parse_geojson_steps(steps)

    ring: list[list[float]] = []
    for idx in range(step_count):
        bearing = (360.0 * idx) / step_count
        p_lat, p_lon = destination_point(lat, lon, bearing, radius)
        ring.append([round(p_lon, 6), round(p_lat, 6)])
    ring.append(list(ring[0]))
    return ring


def build_circle_geojson(
    center_lat: Any,
    center_lon: Any,
    radius_km: Any,
    *,
    steps: Any = 72,
) -> dict[str, object]:
    lat = parse_latitude(center_lat)
    lon = parse_longitude(center_lon)
    radius = parse_radius_km(radius_km)
    ring = build_circle_ring(lat, lon, radius, steps=steps)
    return {
        "type": "Feature",
        "properties": {
            "center": [round(lon, 6), round(lat, 6)],
            "radius_km": round(radius, 6),
            "kind": "location_selector_circle",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [ring],
        },
    }


def sample_points_within_radius(
    center_lat: Any,
    center_lon: Any,
    radius_km: Any,
    *,
    count: Any,
    seed: Any,
) -> list[tuple[float, float]]:
    lat = parse_latitude(center_lat)
    lon = parse_longitude(center_lon)
    radius = parse_radius_km(radius_km)
    sample_count = parse_sample_count(count)
    rng = random.Random(parse_seed(seed))

    out: list[tuple[float, float]] = []
    for _ in range(sample_count):
        bearing = rng.uniform(0.0, 360.0)
        distance = radius * math.sqrt(rng.random())
        point_lat, point_lon = destination_point(lat, lon, bearing, distance)
        out.append((point_lat, point_lon))
    return out


def haversine_distance_km(
    lat_a: float,
    lon_a: float,
    lat_b: float,
    lon_b: float,
) -> float:
    lat1 = math.radians(lat_a)
    lon1 = math.radians(lon_a)
    lat2 = math.radians(lat_b)
    lon2 = math.radians(lon_b)
    d_lat = lat2 - lat1
    d_lon = lon2 - lon1
    a = (
        math.sin(d_lat / 2.0) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_KM * c


def points_to_csv_text(points: list[tuple[float, float]]) -> str:
    if not points:
        raise ValueError(
            _location_error(
                "Save points CSV",
                "no sampled points are available",
                "generate sample points before saving CSV",
            )
        )
    lines = ["latitude,longitude"]
    for lat, lon in points:
        lines.append(f"{lat:.6f},{lon:.6f}")
    return "\n".join(lines) + "\n"


def write_points_csv(path: Any, points: list[tuple[float, float]]) -> Path:
    if not isinstance(path, str) or path.strip() == "":
        raise ValueError(
            _location_error(
                "Save points CSV",
                "output path is required",
                "choose a valid CSV output path",
            )
        )
    output_path = Path(path.strip())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    csv_text = points_to_csv_text(points)
    output_path.write_text(csv_text, encoding="utf-8")
    return output_path
