"""Tests for coding_client.llm.context."""

from __future__ import annotations

import httpx
import pytest
from coding_client.llm.context import (
    apply_request_headers,
    capture_response_metadata,
    install_response_sink,
    llm_request_context,
    reset_response_sink,
)


@pytest.mark.asyncio
async def test_request_headers_injected_via_event_hook():
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        for key, value in request.headers.items():
            captured[key.lower()] = value
        return httpx.Response(200, headers={"X-Inference-Id": "inf-1"}, json={})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        event_hooks={
            "request": [apply_request_headers],
            "response": [capture_response_metadata],
        },
    ) as client:
        with llm_request_context(
            tenant_id="t-1",
            job_id="j-1",
            license_id="l-1",
            schema_id="s-1",
        ):
            await client.get("http://test/x")

    assert captured["x-tenant-id"] == "t-1"
    assert captured["x-job-id"] == "j-1"
    assert captured["x-license-id"] == "l-1"
    assert captured["x-schema-id"] == "s-1"


@pytest.mark.asyncio
async def test_response_metadata_captured_into_sink():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "X-Inference-Id": "inf-42",
                "X-Failover-Chain-Id": "chain-7",
            },
            json={},
        )

    transport = httpx.MockTransport(handler)
    sink: dict[str, str] = {}
    token = install_response_sink(sink)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            event_hooks={
                "request": [apply_request_headers],
                "response": [capture_response_metadata],
            },
        ) as client:
            await client.get("http://test/x")
    finally:
        reset_response_sink(token)

    assert sink == {"inference_id": "inf-42", "failover_chain_id": "chain-7"}


@pytest.mark.asyncio
async def test_no_headers_outside_context():
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        for key in ("x-tenant-id", "x-job-id", "x-license-id", "x-schema-id"):
            if key in request.headers:
                captured[key] = request.headers[key]
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        event_hooks={"request": [apply_request_headers]},
    ) as client:
        await client.get("http://test/x")

    assert captured == {}
