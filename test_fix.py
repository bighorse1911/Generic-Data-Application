#!/usr/bin/env python3
from pathlib import Path
import json

print("=" * 60)
print("STEP 1: Check if placeholder exists in fixture")
print("=" * 60)

fixture = Path("tests/fixtures/default_schema_project.json")
with open(fixture) as f:
    data = json.load(f)

has_placeholder = False
for t in data.get("tables", []):
    for c in t.get("columns", []):
        params = c.get("params", {})
        if params.get("path") == "__CITY_COUNTRY_CSV__":
            has_placeholder = True
            print(f"✓ Found placeholder in {t['table_name']}.{c['name']}")

if not has_placeholder:
    print("⚠ No placeholder __CITY_COUNTRY_CSV__ found in fixture")

print("\n" + "=" * 60)
print("STEP 2: Test placeholder resolution")
print("=" * 60)

from src.schema_project_io import load_project_from_json
proj = load_project_from_json(str(fixture))

csv_paths = []
for t in proj.tables:
    for c in t.columns:
        if c.params and c.params.get("path"):
            path = c.params.get("path")
            exists = Path(path).exists()
            csv_paths.append((t.table_name, c.name, path, exists))
            print(f"  {t.table_name}.{c.name}")
            print(f"    Path: {path}")
            print(f"    Exists: {'✓' if exists else '✗'}")

if not csv_paths:
    print("No CSV paths found in loaded project")
    
print("\n" + "=" * 60)
print("STEP 3: Verify resolution works in generation")
print("=" * 60)

from src.generator_project import generate_project_rows
try:
    rows = generate_project_rows(proj)
    print(f"✓ Generation succeeded! Generated {sum(len(r) for r in rows.values())} total rows")
except Exception as e:
    print(f"✗ Generation failed: {e}")
