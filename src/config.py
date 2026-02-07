from dataclasses import dataclass

@dataclass(frozen=True)
class AppConfig:
    debug: bool = True
    log_level: str = "DEBUG"  # change to "INFO" later
    sqlite_db_path: str = "synthetic.db"
    default_rows: int = 100
    seed: int = 1  # repeatable synthetic data
