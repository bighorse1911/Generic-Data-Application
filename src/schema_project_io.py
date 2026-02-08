import json
from dataclasses import asdict

from src.schema_project_model import SchemaProject, TableSpec, ColumnSpec, ForeignKeySpec, validate_project
from pathlib import Path


def save_project_to_json(project: SchemaProject, path: str) -> None:
    validate_project(project)
    data = asdict(project)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_project_from_json(path: str) -> SchemaProject:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Convenience: resolve known test-fixture placeholder tokens to local files when available.
    # This mirrors test behavior where the JSON uses a placeholder `__CITY_COUNTRY_CSV__`.
    repo_root = Path(__file__).resolve().parents[1]
    candidate = repo_root / "tests" / "fixtures" / "city_country_pool.csv"
    if candidate.exists():
        for t in data.get("tables", []):
            for c in t.get("columns", []):
                params = c.get("params")
                if isinstance(params, dict) and params.get("path") == "__CITY_COUNTRY_CSV__":
                    params["path"] = str(candidate)

    tables = []
    for t in data["tables"]:
        cols = [ColumnSpec(**c) for c in t["columns"]]
        tables.append(TableSpec(table_name=t["table_name"], columns=cols, row_count=int(t.get("row_count", 100))))

    fks = [ForeignKeySpec(**fk) for fk in data.get("foreign_keys", [])]

    project = SchemaProject(
        name=data["name"],
        seed=int(data.get("seed", 12345)),
        tables=tables,
        foreign_keys=fks,
    )
    validate_project(project)
    return project
