import unittest

from src.generator_project import generate_project_rows
from src.schema_project_model import ColumnSpec, SchemaProject, TableSpec, validate_project


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n == 0 or len(ys) != n:
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = 0.0
    den_x = 0.0
    den_y = 0.0
    for x, y in zip(xs, ys):
        dx = x - mean_x
        dy = y - mean_y
        num += dx * dy
        den_x += dx * dx
        den_y += dy * dy
    if den_x <= 0.0 or den_y <= 0.0:
        return 0.0
    return num / ((den_x ** 0.5) * (den_y ** 0.5))


def _ranks(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0 for _ in values]
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1][1] == ordered[i][1]:
            j += 1
        avg_rank = ((i + j) / 2.0) + 1.0
        for idx in range(i, j + 1):
            ranks[ordered[idx][0]] = avg_rank
        i = j + 1
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> float:
    return _pearson(_ranks(xs), _ranks(ys))


class TestCorrelatedColumnGroups(unittest.TestCase):
    def _project(self, *, with_groups: bool) -> SchemaProject:
        return SchemaProject(
            name="dg01_profile",
            seed=20260222,
            tables=[
                TableSpec(
                    table_name="profiles",
                    row_count=600,
                    columns=[
                        ColumnSpec("profile_id", "int", nullable=False, primary_key=True),
                        ColumnSpec(
                            "engagement_score",
                            "decimal",
                            nullable=False,
                            generator="normal",
                            params={"mean": 50.0, "stdev": 10.0, "min": 0.0, "max": 100.0, "decimals": 2},
                        ),
                        ColumnSpec(
                            "spend_score",
                            "decimal",
                            nullable=False,
                            generator="normal",
                            params={"mean": 500.0, "stdev": 130.0, "min": 50.0, "max": 950.0, "decimals": 2},
                        ),
                        ColumnSpec(
                            "segment",
                            "text",
                            nullable=False,
                            generator="choice_weighted",
                            params={"choices": ["bronze", "silver", "gold"], "weights": [0.6, 0.3, 0.1]},
                        ),
                    ],
                    correlation_groups=(
                        [
                            {
                                "group_id": "score_bundle",
                                "columns": ["engagement_score", "spend_score", "segment"],
                                "rank_correlation": [
                                    [1.0, 0.82, 0.55],
                                    [0.82, 1.0, 0.50],
                                    [0.55, 0.50, 1.0],
                                ],
                                "categorical_orders": {"segment": ["bronze", "silver", "gold"]},
                                "strength": 1.0,
                            }
                        ]
                        if with_groups
                        else None
                    ),
                )
            ],
            foreign_keys=[],
        )

    def test_validate_rejects_invalid_rank_correlation_shape(self):
        bad = SchemaProject(
            name="bad_shape",
            seed=7,
            tables=[
                TableSpec(
                    table_name="t",
                    row_count=5,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec("x", "decimal", nullable=False),
                        ColumnSpec("y", "decimal", nullable=False),
                    ],
                    correlation_groups=[
                        {
                            "group_id": "g1",
                            "columns": ["x", "y"],
                            "rank_correlation": [[1.0, 0.8]],
                        }
                    ],
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            validate_project(bad)
        msg = str(ctx.exception)
        self.assertIn("rank_correlation", msg)
        self.assertIn("Fix:", msg)

    def test_validate_rejects_depends_on_columns_inside_group(self):
        bad = SchemaProject(
            name="bad_depends",
            seed=7,
            tables=[
                TableSpec(
                    table_name="t",
                    row_count=5,
                    columns=[
                        ColumnSpec("id", "int", nullable=False, primary_key=True),
                        ColumnSpec("x", "decimal", nullable=False),
                        ColumnSpec("y", "decimal", nullable=False, depends_on=["x"]),
                    ],
                    correlation_groups=[
                        {
                            "group_id": "g1",
                            "columns": ["x", "y"],
                            "rank_correlation": [[1.0, 0.7], [0.7, 1.0]],
                        }
                    ],
                )
            ],
            foreign_keys=[],
        )

        with self.assertRaises(ValueError) as ctx:
            validate_project(bad)
        msg = str(ctx.exception)
        self.assertIn("depends_on", msg)
        self.assertIn("Fix:", msg)

    def test_generation_is_deterministic_and_applies_rank_correlation(self):
        project = self._project(with_groups=True)
        baseline = self._project(with_groups=False)
        validate_project(project)
        validate_project(baseline)

        rows_a = generate_project_rows(project)["profiles"]
        rows_b = generate_project_rows(project)["profiles"]
        self.assertEqual(rows_a, rows_b)

        baseline_rows = generate_project_rows(baseline)["profiles"]
        for col_name in ("engagement_score", "spend_score", "segment"):
            self.assertCountEqual(
                [row[col_name] for row in rows_a],
                [row[col_name] for row in baseline_rows],
            )

        engagement = [float(row["engagement_score"]) for row in rows_a]
        spend = [float(row["spend_score"]) for row in rows_a]
        segment_order = {"bronze": 0.0, "silver": 1.0, "gold": 2.0}
        segment = [segment_order[str(row["segment"])] for row in rows_a]

        corr_eng_spend = _spearman(engagement, spend)
        corr_eng_segment = _spearman(engagement, segment)
        self.assertGreater(
            corr_eng_spend,
            0.70,
            "Expected strong positive rank correlation between engagement_score and spend_score.",
        )
        self.assertGreater(
            corr_eng_segment,
            0.35,
            "Expected positive rank correlation between engagement_score and segment ordering.",
        )


if __name__ == "__main__":
    unittest.main()

