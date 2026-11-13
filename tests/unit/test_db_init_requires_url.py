"""``coding_client.db_init`` has no host default DSN (George ruling 2026-10-21)."""

import importlib
import sys

import pytest


def _fresh_import():
    sys.modules.pop("coding_client.db_init", None)
    return importlib.import_module("coding_client.db_init")


def test_import_refuses_without_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    try:
        with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
            _fresh_import()
    finally:
        sys.modules.pop("coding_client.db_init", None)


def test_import_honours_explicit_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    # Engine creation is lazy: no connection is attempted at import.
    monkeypatch.setenv("DATABASE_URL", "postgresql://svc@db.invalid:6543/x")
    try:
        mod = _fresh_import()
        assert mod.DATABASE_URL == "postgresql+psycopg://svc@db.invalid:6543/x"
        assert mod.engine.url.host == "db.invalid"
    finally:
        sys.modules.pop("coding_client.db_init", None)
