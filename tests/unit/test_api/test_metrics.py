"""Tests for coding_client.api.metrics middleware."""

from __future__ import annotations

import pytest
from coding_client.api.metrics import add_process_time_header
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


def _build_app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(add_process_time_header)

    @app.get("/api/thing")
    async def thing():
        return {"ok": True}

    return app


@pytest.mark.asyncio
async def test_adds_process_time_header() -> None:
    transport = ASGITransport(app=_build_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/thing")
    assert resp.status_code == 200
    assert "x-process-time" in resp.headers
    # Header is a float-formatted duration in seconds.
    assert float(resp.headers["x-process-time"]) >= 0.0
