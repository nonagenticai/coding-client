"""Tests for ``coding_client.api.logging_setup.configure_logging``."""

from __future__ import annotations

import logging

import pytest
from coding_client.api.logging_setup import _DEFAULT_FORMAT, configure_logging


@pytest.fixture(autouse=True)
def _reset_root_logger():
    """Snapshot the root logger and restore it so tests don't leak handlers."""
    root = logging.getLogger()
    saved_level = root.level
    saved_handlers = list(root.handlers)
    try:
        yield
    finally:
        for h in list(root.handlers):
            root.removeHandler(h)
        for h in saved_handlers:
            root.addHandler(h)
        root.setLevel(saved_level)


def test_default_level_is_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    configure_logging()
    assert logging.getLogger().level == logging.INFO


def test_env_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    configure_logging()
    assert logging.getLogger().level == logging.DEBUG


def test_default_argument_used_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    configure_logging(default_level="WARNING")
    assert logging.getLogger().level == logging.WARNING


def test_env_takes_priority_over_argument(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "ERROR")
    configure_logging(default_level="DEBUG")
    assert logging.getLogger().level == logging.ERROR


def test_invalid_level_falls_back_to_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "BOGUS")
    configure_logging()
    assert logging.getLogger().level == logging.INFO


def test_force_overwrites_existing_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    root = logging.getLogger()
    pre_existing = logging.NullHandler()
    root.addHandler(pre_existing)
    configure_logging()
    assert pre_existing not in root.handlers
    assert any(isinstance(h, logging.StreamHandler) for h in root.handlers)


def test_format_uses_default_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    configure_logging()
    handler = next(h for h in logging.getLogger().handlers if isinstance(h, logging.StreamHandler))
    assert handler.formatter is not None
    assert handler.formatter._fmt == _DEFAULT_FORMAT
