#!/usr/bin/env python3
from pathlib import Path
import json


def main() -> None:
    print("=" * 60)
    print("STEP 1: Check if placeholder exists in fixture")
    print("=" * 60)

    fixture = Path("tests/fixtures/default_schema_project.json")
    with open(fixture, encoding="utf-8") as f:
        data = json.load(f)

    has_placeholder = False
    for table in data.get("tables", []):
        for column in table.get("columns", []):
            params = column.get("params")
            if not isinstance(params, dict):
                continue
            if params.get("path") == "__CITY_COUNTRY_CSV__":
                has_placeholder = True
                print(f"+ Found placeholder in {table['table_name']}.{column['name']}")

    if not has_placeholder:
        print("! No placeholder __CITY_COUNTRY_CSV__ found in fixture")

    print("\n" + "=" * 60)
    print("STEP 2: Test placeholder resolution")
    print("=" * 60)

    from src.schema_project_io import load_project_from_json

    project = load_project_from_json(str(fixture))

    csv_paths: list[tuple[str, str, str, bool]] = []
    for table in project.tables:
        for column in table.columns:
            if column.params and column.params.get("path"):
                path = str(column.params.get("path"))
                exists = Path(path).exists()
                csv_paths.append((table.table_name, column.name, path, exists))
                print(f"  {table.table_name}.{column.name}")
                print(f"    Path: {path}")
                print(f"    Exists: {'+' if exists else 'x'}")

    if not csv_paths:
        print("No CSV paths found in loaded project")

    print("\n" + "=" * 60)
    print("STEP 3: Verify resolution works in generation")
    print("=" * 60)

    from src.generator_project import generate_project_rows

    try:
        rows = generate_project_rows(project)
        print(f"+ Generation succeeded! Generated {sum(len(r) for r in rows.values())} total rows")
    except Exception as exc:
        print(f"x Generation failed: {exc}")


if __name__ == "__main__":
    main()
