import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.location_selector import (
    build_circle_geojson,
    haversine_distance_km,
    parse_geojson_steps,
    parse_latitude,
    parse_longitude,
    parse_radius_km,
    points_to_csv_text,
    sample_points_within_radius,
    write_points_csv,
)


class TestLocationSelector(unittest.TestCase):
    def test_build_circle_geojson_returns_closed_polygon(self):
        feature = build_circle_geojson(-33.8688, 151.2093, 100.0, steps=64)

        self.assertEqual(feature.get("type"), "Feature")
        self.assertEqual(feature.get("geometry", {}).get("type"), "Polygon")
        coordinates = feature.get("geometry", {}).get("coordinates")
        self.assertIsInstance(coordinates, list)
        self.assertTrue(coordinates)
        ring = coordinates[0]
        self.assertEqual(len(ring), 65)
        self.assertEqual(ring[0], ring[-1])
        self.assertEqual(feature.get("properties", {}).get("radius_km"), 100.0)

    def test_sample_points_are_deterministic_and_within_radius(self):
        center_lat = -33.8688
        center_lon = 151.2093
        radius_km = 100.0

        points_a = sample_points_within_radius(
            center_lat,
            center_lon,
            radius_km,
            count=250,
            seed=42,
        )
        points_b = sample_points_within_radius(
            center_lat,
            center_lon,
            radius_km,
            count=250,
            seed=42,
        )
        self.assertEqual(points_a, points_b)

        for lat, lon in points_a:
            distance = haversine_distance_km(center_lat, center_lon, lat, lon)
            self.assertLessEqual(
                distance,
                radius_km + 1e-6,
                "Location selector sampled a point outside configured radius. "
                "Fix: keep point sampling bounded by radius_km.",
            )

    def test_validation_errors_are_actionable(self):
        with self.assertRaises(ValueError) as lat_ctx:
            parse_latitude("abc")
        lat_msg = str(lat_ctx.exception)
        self.assertIn("Location Selector / Latitude", lat_msg)
        self.assertIn("Fix:", lat_msg)

        with self.assertRaises(ValueError) as lon_ctx:
            parse_longitude(220)
        lon_msg = str(lon_ctx.exception)
        self.assertIn("Location Selector / Longitude", lon_msg)
        self.assertIn("Fix:", lon_msg)

        with self.assertRaises(ValueError) as radius_ctx:
            parse_radius_km(0)
        radius_msg = str(radius_ctx.exception)
        self.assertIn("Location Selector / Radius (km)", radius_msg)
        self.assertIn("Fix:", radius_msg)

        with self.assertRaises(ValueError) as steps_ctx:
            parse_geojson_steps(5)
        steps_msg = str(steps_ctx.exception)
        self.assertIn("Location Selector / GeoJSON resolution", steps_msg)
        self.assertIn("Fix:", steps_msg)

    def test_points_to_csv_text_formats_rows(self):
        text = points_to_csv_text([(10.1234567, 20.7654321), (-1.5, 2.5)])
        self.assertEqual(
            text,
            "latitude,longitude\n10.123457,20.765432\n-1.500000,2.500000\n",
        )

    def test_points_to_csv_text_empty_is_actionable(self):
        with self.assertRaises(ValueError) as ctx:
            points_to_csv_text([])
        msg = str(ctx.exception)
        self.assertIn("Location Selector / Save points CSV", msg)
        self.assertIn("Fix:", msg)

    def test_write_points_csv_writes_expected_output(self):
        with TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "points.csv"
            written = write_points_csv(str(out_path), [(-33.9, 151.2), (-34.0, 151.3)])
            self.assertEqual(written, out_path)
            self.assertTrue(out_path.exists())
            content = out_path.read_text(encoding="utf-8")
            self.assertEqual(
                content,
                "latitude,longitude\n-33.900000,151.200000\n-34.000000,151.300000\n",
            )


if __name__ == "__main__":
    unittest.main()
