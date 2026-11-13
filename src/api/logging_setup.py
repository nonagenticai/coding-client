"""Root logger configuration for coding-* microservices.

Without ``logging.basicConfig()``, application module loggers
(``logger = logging.getLogger(__name__)``) get no handler from uvicorn's
default ``LOGGING_CONFIG`` -- which only configures the ``uvicorn.*`` loggers,
not the root. The result is that every ``logger.info(...)`` call from app
code is silently dropped (Python's "last resort" handler emits only WARNING+).

This module provides a single entry point that all services should call
before lifespan emits its first log line, so log format and level handling
stay consistent across the fleet.
"""

from __future__ import annotations

import logging
import os

__all__ = ["configure_logging"]

_DEFAULT_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_logging(default_level: str = "INFO") -> None:
    """Configure the root logger so ALL module loggers get a handler.

    Reads ``LOG_LEVEL`` from the environment (defaulting to ``default_level``),
    installs a stream handler with a consistent format, and uses
    ``force=True`` to overwrite any handler uvicorn or another framework may
    have already attached.

    Call this once at startup, before any application code emits log records:

    - For module-level FastAPI apps, call it at the top of ``main.py``,
      before ``logger = logging.getLogger(__name__)``.
    - For factory-style apps, call it as the first statement inside
      ``create_app()``.
    """
    log_level = os.getenv("LOG_LEVEL", default_level).upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format=_DEFAULT_FORMAT,
        force=True,
    )
