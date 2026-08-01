"""Application logging helpers."""

from __future__ import annotations

import logging
import sys
from functools import lru_cache


def setup_logging(level: str = "INFO") -> None:
    """Configure root logging once for the process."""
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root.addHandler(handler)
    root.setLevel(level)


@lru_cache(maxsize=64)
def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)
