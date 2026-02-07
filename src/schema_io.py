import json
from dataclasses import asdict

from src.schema_model import TableSchema, ColumnSpec, validate_schema

def save_schema_to_json(schema: TableSchema, path: str) -> None:
    validate_schema(schema)
    data = asdict(schema)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_schema_from_json(path: str) -> TableSchema:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cols = [ColumnSpec(**c) for c in data["columns"]]
    schema = TableSchema(
        table_name=data["table_name"],
        columns=cols,
        seed=int(data.get("seed", 12345)),
    )
    validate_schema(schema)
    return schema
