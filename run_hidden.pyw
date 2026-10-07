from __future__ import annotations

import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
LOG_DIR = PROJECT_DIR / "logs"
LOG_FILE = LOG_DIR / "bridge.log"
RESTART_DELAY_SECONDS = 30


class LoggerWriter:
    """Redirect print output from the bridge into the rotating log."""

    def __init__(self, logger: logging.Logger, level: int) -> None:
        self.logger = logger
        self.level = level

    def write(self, message: str) -> int:
        for line in message.rstrip().splitlines():
            self.logger.log(self.level, line)
        return len(message)

    def flush(self) -> None:
        for handler in self.logger.handlers:
            handler.flush()


def configure_logging() -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger("ps3-discord-presence")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def run() -> int:
    logger = configure_logging()
    sys.stdout = LoggerWriter(logger, logging.INFO)  # type: ignore[assignment]
    sys.stderr = LoggerWriter(logger, logging.ERROR)  # type: ignore[assignment]
    logger.info("Autostart launcher started.")

    while True:
        try:
            from gui import main

            exit_code = main(["--tray"])
        except Exception:
            logger.exception("Application terminated unexpectedly.")
            exit_code = 1

        if exit_code == 0:
            logger.info("Application closed by user.")
            return 0

        logger.warning("Application stopped with exit code %s; restarting in %s seconds.", exit_code, RESTART_DELAY_SECONDS)
        time.sleep(RESTART_DELAY_SECONDS)


if __name__ == "__main__":
    raise SystemExit(run())
