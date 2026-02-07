import logging
import traceback

from config import AppConfig
from logging_setup import setup_logging
from app import run_app

logger = logging.getLogger("main")

def main() -> int:
    cfg = AppConfig()

    setup_logging(cfg.log_level)
    logger.info("App booting...")

    try:
        run_app(cfg)
        return 0
    except Exception as exc:
        logger.error("Unhandled error: %s", exc)
        if cfg.debug:
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
