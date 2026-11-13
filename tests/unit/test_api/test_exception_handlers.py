"""Regression tests for ``coding_client.api.exception_handlers``.

Anchors the contract that the KAG-standard handler must recognise both
``starlette.exceptions.HTTPException`` (raised by FastAPI's router for 404s,
405s, etc.) and the FastAPI-derived ``fastapi.HTTPException``.

A 1.3.0 regression had ``_handle_http`` doing ``isinstance(exc, fastapi.HTTPException)``
which misses the starlette base class — every routing 404 fell back to a
synthetic ``HTTPException(status_code=500)``, masking the real status code.
"""

from __future__ import annotations

import pytest
from coding_client.api.exception_handlers import register_exception_handlers
from fastapi import FastAPI
from fastapi import HTTPException as FastAPIHTTPException
from httpx import ASGITransport, AsyncClient
from starlette.exceptions import HTTPException as StarletteHTTPException


def _build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/raise-fastapi-http")
    async def raise_fastapi_http():
        raise FastAPIHTTPException(status_code=403, detail="forbidden via fastapi")

    @app.get("/raise-starlette-http")
    async def raise_starlette_http():
        raise StarletteHTTPException(status_code=418, detail="teapot via starlette")

    return app


@pytest.mark.asyncio
async def test_route_404_returns_404_envelope() -> None:
    """FastAPI's router raises starlette.HTTPException for unmatched routes."""
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/nope")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "HTTP_404"
    assert "request_id" in body["error"]


@pytest.mark.asyncio
async def test_fastapi_httpexception_preserves_status_and_detail() -> None:
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/raise-fastapi-http")
    assert resp.status_code == 403
    body = resp.json()
    assert body["error"]["code"] == "HTTP_403"
    assert body["error"]["message"] == "forbidden via fastapi"


@pytest.mark.asyncio
async def test_starlette_httpexception_preserves_status_and_detail() -> None:
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/raise-starlette-http")
    assert resp.status_code == 418
    body = resp.json()
    assert body["error"]["code"] == "HTTP_418"
    assert body["error"]["message"] == "teapot via starlette"
