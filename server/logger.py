"""
server/logger.py

Central logging setup for the entire MCP project.
Every file imports get_logger() from here.

Usage in any file:
    from server.logger import get_logger
    logger = get_logger(__name__)
"""

import logging
import logging.handlers
from server import config


def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger for the given module name.
    Call this at the top of any file that needs logging.

    Example:
        logger = get_logger(__name__)
        logger.info("Tool called")
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if logger already configured
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # ── Format ────────────────────────────────
    formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # ── Console Handler (shows in terminal) ───
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # ── File Handler (saves to logs/) ─────────
    file_handler = logging.handlers.RotatingFileHandler(
        filename=config.LOG_FILE,
        maxBytes=5 * 1024 * 1024,   # 5 MB max per log file
        backupCount=3,               # keeps 3 old log files
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger