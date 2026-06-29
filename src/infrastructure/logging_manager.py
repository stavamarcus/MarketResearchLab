"""
LoggingManager — centrální konfigurace loggingu pro Market Research Lab.

Použití:
    from src.infrastructure.logging_manager import get_logger
    logger = get_logger(__name__)
"""

import logging
import sys
from pathlib import Path


def configure_logging(
    level: int = logging.INFO,
    log_file: Path | None = None,
) -> None:
    """
    Nastaví root logger pro MRL.

    Volat jednou při startu aplikace (main.py).
    Všechny get_logger() volání dědí tuto konfiguraci.
    """
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt=datefmt,
        handlers=handlers,
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Vrátí pojmenovaný logger."""
    return logging.getLogger(name)
