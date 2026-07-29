"""Structured logging setup.

Configures a single JSON-friendly logger per the project's `BFSI_LOG_LEVEL`
env var. Idempotent — safe to call multiple times.
"""

from __future__ import annotations

import logging
import sys
from typing import Final

_CONFIGURED: bool = False
_LOGGER_NAME: Final[str] = "bfsi_rbi"


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger once. Subsequent calls are no-ops."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric_level)

    # Quiet noisy third-party loggers
    for noisy in ("httpx", "httpcore", "elastic_transport", "litellm"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger under the bfsi_rbi namespace."""
    if name is None:
        return logging.getLogger(_LOGGER_NAME)
    if not name.startswith(_LOGGER_NAME):
        name = f"{_LOGGER_NAME}.{name}"
    return logging.getLogger(name)
