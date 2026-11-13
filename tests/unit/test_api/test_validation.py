"""Tests for coding_client.api.validation middleware."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from coding_client.api.validation import (
    SecurityValidationException,
    ValidationMiddleware,
)
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


class TestPreprocessRequest:
    """URL normalisation helper."""

    def test_collapses_repeated_slashes(self):
        assert ValidationMiddleware._preprocess_request("/a//b///c") == "/a/b/c"

    def test_strips_trailing_slash(self):
        assert ValidationMiddleware._preprocess_request("/a/b/") == "/a/b"

    def test_keeps_root_slash(self):
        assert ValidationMiddleware._preprocess_request("/") == "/"

    def test_decodes_percent_encoding(self):
        assert ValidationMiddleware._preprocess_request("/a%20b") == "/a b"


class TestValidateRequestSecurity:
    """Control-character rejection."""

    def _request(self, url: str):
        # ValidationMiddleware._validate_request_security only reads str(request.url).
        return SimpleNamespace(url=url)

    def test_rejects_control_char(self):
        mw = ValidationMiddleware(app=None)
        with pytest.raises(SecurityValidationException) as exc_info:
            mw._validate_request_security(self._request("http://x/a\x00b"))
        assert exc_info.value.error_code == "CONTROL_CHAR_DETECTED"

    def test_allows_clean_url(self):
        mw = ValidationMiddleware(app=None)
        # Should not raise
        mw._validate_request_security(self._request("http://x/a/b"))


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(ValidationMiddleware)

    @app.get("/api/thing")
    async def thing():
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


@pytest.mark.asyncio
async def test_clean_request_passes_through() -> None:
    transport = ASGITransport(app=_build_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/thing")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


@pytest.mark.asyncio
async def test_excluded_path_skips_validation() -> None:
    transport = ASGITransport(app=_build_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
