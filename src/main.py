# To run:
# python -m src.main


import logging
import traceback
import tkinter as tk
from tkinter import ttk

from src.config import AppConfig
from src.logging_setup import setup_logging
from src.gui_home import App

logger = logging.getLogger("main")


def main() -> int:
    cfg = AppConfig()

    setup_logging(cfg.log_level)
    logger.info("App booting (GUI with home screen)...")

    try:
        root = tk.Tk()
        # ttk = themed widgets that look more native on Windows
        ttk.Style().theme_use("clam")  # optional; comment out if you dislike it
        App(root, cfg)
        root.mainloop()
        return 0
    except Exception as exc:
        logger.error("Unhandled error: %s", exc)
        if cfg.debug:
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
