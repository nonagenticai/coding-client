"""Per-request context plumbing for inference-router headers.

Uses contextvars so that nested asyncio tasks (pydantic-ai schedules child
tasks during a single Agent.run) inherit the routing identity automatically.

Critical: the response-side metadata sink uses a MUTABLE dict pattern. The
parent installs an empty dict via ``ContextVar.set(...)``; the response
event hook ``.update()``s that dict in place. This works across child task
boundaries because asyncio.copy_context shares the reference — whereas a
``.set()`` inside a child task would be invisible to the parent.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    import httpx2 as httpx  # the LLM plane's client — see base_agent.py


_llm_request_context: ContextVar[dict[str, str]] = ContextVar(
    "coding_client_llm_request_context",
    default={},
)
_llm_response_metadata: ContextVar[dict[str, str] | None] = ContextVar(
    "coding_client_llm_response_metadata",
    default=None,
)


@contextmanager
def llm_request_context(
    *,
    tenant_id: str | None = None,
    job_id: str | None = None,
    license_id: str | None = None,
    schema_id: str | None = None,
) -> Iterator[None]:
    """Attach request-scoped routing headers for downstream LLM calls.

    Usage::

        with llm_request_context(tenant_id="t1", job_id="j2"):
            await agent._call_llm(...)
    """
    current = dict(_llm_request_context.get({}))
    updates = {
        key: value
        for key, value in {
            "tenant_id": tenant_id,
            "job_id": job_id,
            "license_id": license_id,
            "schema_id": schema_id,
        }.items()
        if value
    }
    token = _llm_request_context.set({**current, **updates})
    try:
        yield
    finally:
        _llm_request_context.reset(token)


def _current_request_headers() -> dict[str, str]:
    """Build inference-router headers from the current contextvar state."""
    ctx = _llm_request_context.get({})
    headers: dict[str, str] = {}
    if value := ctx.get("tenant_id"):
        headers["X-Tenant-Id"] = value
    if value := ctx.get("job_id"):
        headers["X-Job-Id"] = value
    if value := ctx.get("license_id"):
        headers["X-License-Id"] = value
    if value := ctx.get("schema_id"):
        headers["X-Schema-Id"] = value
    return headers


async def apply_request_headers(request: httpx.Request) -> None:
    """httpx request event hook: inject routing headers just before send."""
    for header, value in _current_request_headers().items():
        request.headers[header] = value


async def capture_response_metadata(response: httpx.Response) -> None:
    """httpx response event hook: write inference-router metadata to sink."""
    sink = _llm_response_metadata.get()
    if sink is None:
        return
    headers = response.headers
    for key, candidates in (
        ("inference_id", ("X-Inference-Id", "inference-id")),
        ("failover_chain_id", ("X-Failover-Chain-Id", "failover-chain-id")),
    ):
        for candidate in candidates:
            value = headers.get(candidate)
            if value:
                sink[key] = value
                break


def install_response_sink(sink: dict[str, str]):
    """Install a metadata sink for the duration of one LLM call.

    Returns the contextvar token; the caller must reset it in a finally.
    """
    return _llm_response_metadata.set(sink)


def reset_response_sink(token) -> None:
    """Reset the response sink contextvar to its prior state."""
    _llm_response_metadata.reset(token)


def current_response_sink() -> dict[str, str] | None:
    """Return the currently installed response sink, if any (test helper)."""
    return _llm_response_metadata.get()
