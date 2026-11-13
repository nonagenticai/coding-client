"""OpenTelemetry trace setup for coding-* services.

One implementation, called once per service at **application-construction time**.

Why this lives in the SDK rather than a per-repo ``telemetry.py``: the wider fleet
copies a ``src/telemetry.py`` into every repo, and those copies drift. Three
coding services each grew their own version of this block and **all three emitted
nothing**, for three different reasons, for months — while logging that tracing
was enabled.

The trap that made them silent is the reason ``setup_tracing`` refuses rather than
returns:

    ``FastAPIInstrumentor.instrument_app(app)`` called inside a FastAPI lifespan
    produces **zero spans and raises nothing**. By the time the lifespan runs,
    Starlette has already built the middleware stack, so the instrumentation is
    discarded silently.

So a late call is a hard error here, named at the call site. Every other failure
mode (no endpoint, SDK disabled, packages absent) is a quiet ``False`` — those are
legitimate local/test configurations, and none of them can be mistaken for
working tracing, because they emit no success log either.

Configuration, matching the fleet convention already provisioned in
``clusters/strato``:

- ``OTLP_TRACES_ENDPOINT`` — full URL including ``/v1/traces``. Unset ⇒ no exporter.
- ``OTEL_SDK_DISABLED`` — ``"true"`` ⇒ no tracing at all.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

#: Probe and scrape paths, excluded so kubelet traffic does not dominate the
#: trace store. Substring-matched by the instrumentation, not anchored.
#: Nine services probed every ~10s would otherwise outweigh every real request
#: the coding fleet serves.
DEFAULT_EXCLUDED_URLS = "health,healthz,metrics,ready,readyz,live,livez"

#: The single span attribute that carries the raw query string. Stripped so a
#: future ``?token=`` parameter cannot reach the trace store. No coding-*
#: route declares a sensitive query parameter today (105 scanned across the
#: fleet); this keeps it that way by construction rather than by review.
_URL_ATTRIBUTES = ("http.url", "url.full")


def _strip_query(url: str) -> str:
    """Drop everything from the first ``?``, keeping scheme/host/path."""
    head, sep, _ = url.partition("?")
    return head if sep else url


def _server_request_hook(span: Any, scope: dict[str, Any]) -> None:
    """Redact the query string from the server span while it is still writable.

    Runs inside the instrumentation with a recording span, which is the only
    point where these attributes can still be overwritten — once the span has
    ended its attributes are frozen.
    """
    if span is None or not getattr(span, "is_recording", lambda: False)():
        return
    for key in _URL_ATTRIBUTES:
        value = (span.attributes or {}).get(key)
        if isinstance(value, str) and "?" in value:
            span.set_attribute(key, _strip_query(value))


def _already_started(app: FastAPI) -> bool:
    """True once Starlette has built the middleware stack.

    After that point ``instrument_app`` is a silent no-op, which is the exact
    failure this module exists to make impossible.
    """
    return getattr(app, "middleware_stack", None) is not None


def _instrument_httpx(provider: Any) -> bool:
    """Instrument outbound httpx calls against ``provider``, best-effort.

    Client spans are what Tempo's ``service_graphs`` processor turns into edges —
    a server-span-only service appears in the graph as a node nothing points at.
    This SDK's own outbound helpers use httpx, so instrumenting it here covers
    every coding-to-coding call without per-service work.

    ``HTTPXClientInstrumentor`` is a process-wide singleton that binds its tracer
    at ``instrument()`` time, so the provider is passed explicitly rather than
    resolved from the global — the same reason it is passed to the FastAPI
    instrumentation. Re-instrumenting an already-instrumented process is a no-op
    in OpenTelemetry, so this rebinds first to guarantee spans reach *this*
    service's provider.
    """
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    except ImportError:
        logger.debug("httpx tracing skipped: opentelemetry-instrumentation-httpx not installed")
        return False

    instrumentor = HTTPXClientInstrumentor()
    if getattr(instrumentor, "is_instrumented_by_opentelemetry", False):
        instrumentor.uninstrument()
    instrumentor.instrument(tracer_provider=provider)
    return True


def setup_tracing(
    app: FastAPI,
    service_name: str,
    *,
    excluded_urls: str | None = None,
    instrument_httpx: bool = True,
) -> bool:
    """Install OTLP tracing on ``app``. Returns True only if spans will be exported.

    Must be called at construction time, before the app serves its first request
    (so: module scope or an app factory — never inside ``lifespan`` or a startup
    handler).

    Args:
        app: The FastAPI application, not yet started.
        service_name: ``service.name`` in Tempo. Use the Kubernetes service name.
        excluded_urls: Comma-separated substrings; defaults to probe/scrape paths.
        instrument_httpx: Also trace outbound httpx calls, so this service becomes
            a *source* of service-graph edges and not only a target. Best-effort:
            a missing ``opentelemetry-instrumentation-httpx`` is not an error.

    Returns:
        True when a tracer provider and OTLP exporter were installed. False when
        tracing is deliberately off (``OTEL_SDK_DISABLED``), unconfigured (no
        ``OTLP_TRACES_ENDPOINT``), or the OpenTelemetry packages are absent.

    Raises:
        RuntimeError: if called after the app has started, because the
            instrumentation would be discarded without any error of its own.
    """
    if _already_started(app):
        raise RuntimeError(
            f"setup_tracing({service_name!r}) was called after the application "
            "started — FastAPIInstrumentor.instrument_app() is a silent no-op at "
            "that point and would export ZERO spans. Move this call to "
            "application-construction time (module scope or the app factory), "
            "not the lifespan or a startup handler."
        )

    if os.getenv("OTEL_SDK_DISABLED", "false").strip().lower() == "true":
        logger.info("tracing disabled: OTEL_SDK_DISABLED=true")
        return False

    endpoint = (os.getenv("OTLP_TRACES_ENDPOINT") or "").strip()
    if not endpoint:
        logger.info("tracing disabled: OTLP_TRACES_ENDPOINT is not set")
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        logger.info("tracing disabled: OpenTelemetry packages not installed (%s)", exc)
        return False

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))

    # Register globally: FastAPIInstrumentor resolves the provider lazily through
    # the global proxy, so an unregistered provider yields non-recording spans and
    # nothing is ever exported.
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=provider,
        excluded_urls=DEFAULT_EXCLUDED_URLS if excluded_urls is None else excluded_urls,
        server_request_hook=_server_request_hook,
    )

    httpx_traced = _instrument_httpx(provider) if instrument_httpx else False

    logger.info(
        "tracing enabled: service=%s endpoint=%s httpx=%s",
        service_name,
        endpoint,
        httpx_traced,
    )
    return True
