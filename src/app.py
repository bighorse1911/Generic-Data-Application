import logging

from src.config import AppConfig
from src.generator import generate_people
from src.storage_sqlite import init_db, insert_people

logger = logging.getLogger("app")

def run_app(cfg: AppConfig) -> None:
    logger.debug("Starting app with config: %s", cfg)

    init_db(cfg.sqlite_db_path)

    print("\n=== Synthetic Data App (MVP) ===")
    raw = input(f"How many rows? (default {cfg.default_rows}): ").strip()
    n = cfg.default_rows if raw == "" else int(raw)

    rows = generate_people(n=n, seed=cfg.seed)
    inserted = insert_people(cfg.sqlite_db_path, rows)

    print(f"✅ Done. Inserted {inserted} rows into {cfg.sqlite_db_path}")
    print("Tip: open the DB with any SQLite viewer, or query it in Python later.")
