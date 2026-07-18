"""
Application logging configuration.
"""

import logging
from pathlib import Path

from config.settings import LOG_LEVEL

# Create the logs directory if it does not exist.

LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOGS_DIR / "app.log"


def _get_log_level() -> int:
    """
    Return the configured logging level.

    Raises:
        ValueError: If LOG_LEVEL is invalid.
    """

    level = getattr(logging, LOG_LEVEL.upper(), None)

    if not isinstance(level, int):
        raise ValueError(
            f"Invalid LOG_LEVEL: '{LOG_LEVEL}'. "
            "Expected DEBUG, INFO, WARNING, ERROR, or CRITICAL."
        )

    return level


def get_logger(name: str) -> logging.Logger:
    """
    Return a configured logger.

    The logger writes messages to both the console and logs/app.log.
    """

    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(_get_log_level())
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logger.level)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(
        filename=LOG_FILE,
        encoding="utf-8",
        delay=True,
    )
    file_handler.setLevel(logger.level)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
