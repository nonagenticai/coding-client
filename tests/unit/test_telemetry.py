"""Tests for src/telemetry.py.

These assert **exported spans**, not that a mock was called. That distinction is
the whole point: three coding services shipped tracing code that called every
right function in the right order and exported nothing, and a mock-based test
would have passed against all three.
"""

from __future__ import annotations

import builtins
from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from src.telemetry import DEFAULT_EXCLUDED_URLS, _strip_query, setup_tracing

ENDPOINT = "http://tempo.tempo.svc.cluster.local:4318/v1/traces"

#: Captured before any test patches it. The ``collector`` fixture replaces
#: ``TracerProvider.add_span_processor`` class-wide, so a test that needs to build
#: a provider the collector does NOT capture must add its processor through this.
_REAL_ADD_SPAN_PROCESSOR = TracerProvider.add_span_processor


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate each test from ambient config and from the previous test's provider.

    ``trace.set_tracer_provider`` is **set-once per process**: the second call is
    ignored (with a log line, not an exception). That is correct in production —
    each service calls ``setup_tracing`` once — but in a suite it means test #2
    onwards would silently observe test #1's provider. Resetting the module
    globals is the standard OpenTelemetry test approach and is what makes
    ``test_provider_is_registered_globally`` able to fail.
    """
    monkeypatch.delenv("OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)

    from opentelemetry import trace
    from opentelemetry.util._once import Once

    monkeypatch.setattr(trace, "_TRACER_PROVIDER", None, raising=False)
    monkeypatch.setattr(trace, "_TRACER_PROVIDER_SET_ONCE", Once(), raising=False)


@pytest.fixture
def collector(monkeypatch: pytest.MonkeyPatch):
    """Capture spans in memory instead of shipping them to Tempo.

    Patches the exporter symbol *where telemetry.py imports it from*, so the real
    ``setup_tracing`` code path — provider, processor, global registration,
    instrumentation — runs unchanged.
    """
    monkeypatch.setenv("OTLP_TRACES_ENDPOINT", ENDPOINT)
    exporter = InMemorySpanExporter()

    def add_in_memory(self: TracerProvider, _processor: object) -> None:
        _REAL_ADD_SPAN_PROCESSOR(self, SimpleSpanProcessor(exporter))

    monkeypatch.setattr(TracerProvider, "add_span_processor", add_in_memory)
    return exporter


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/thing")
    def thing() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    return app


def _drive(
    app: FastAPI,
    path: str = "/api/thing",
    headers: dict[str, str] | None = None,
) -> int:
    with TestClient(app) as client:
        return client.get(path, headers=headers).status_code


# --------------------------------------------------------------------------
# The behaviour that makes this module worth existing
# --------------------------------------------------------------------------


def test_construction_time_call_exports_spans(collector: InMemorySpanExporter) -> None:
    """The supported call site actually produces spans."""
    app = _app()
    assert setup_tracing(app, "coding-test") is True

    assert _drive(app) == 200

    spans = collector.get_finished_spans()
    assert spans, "no spans exported — setup_tracing did not instrument the app"
    assert any(s.name == "GET /api/thing" for s in spans), [s.name for s in spans]


def test_provider_is_registered_globally(collector: InMemorySpanExporter) -> None:
    """coding-ai's real bug: build a provider, never register it globally.

    ``instrument_app`` is given the provider explicitly here, so FastAPI spans
    survive that omission and every other test in this file still passes — this
    mutant went undetected until the mutation run. It matters because everything
    that is *not* the FastAPI instrumentation resolves the provider through the
    global proxy: ``HTTPXClientInstrumentor`` (coding-security and coding-gateway
    both declare it), and any ``trace.get_tracer(__name__)`` in service code.
    Without registration those produce non-recording spans and export nothing,
    which silently costs the client half of every service-graph edge.
    """
    from opentelemetry import trace

    app = _app()
    assert setup_tracing(app, "coding-test") is True

    tracer = trace.get_tracer("probe-not-the-fastapi-instrumentation")
    with tracer.start_as_current_span("manual-span"):
        pass

    names = [s.name for s in collector.get_finished_spans()]
    assert "manual-span" in names, (
        "the global tracer produced no exported span — trace.set_tracer_provider() "
        f"was not called; got {names}"
    )


def test_lifespan_call_raises_instead_of_silently_doing_nothing() -> None:
    """The trap: instrument_app inside a lifespan exports zero spans and raises nothing.

    Measured in the real coding-security image (starlette 1.3.1, fastapi 0.136.1,
    opentelemetry-instrumentation-fastapi 0.60b1): construction → 3 spans,
    lifespan → 0 spans and no exception. setup_tracing must turn that silence
    into a loud failure, or the defect is reintroducible by a one-line move.
    """
    captured: dict[str, BaseException] = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            setup_tracing(app, "coding-test")
        except BaseException as exc:  # noqa: BLE001 - recording it is the assertion
            captured["error"] = exc
        yield

    app = FastAPI(lifespan=lifespan)
    with TestClient(app):
        pass

    assert "error" in captured, (
        "setup_tracing returned instead of raising when called after startup — "
        "that is exactly the silent no-op this guard exists to prevent"
    )
    error = captured["error"]
    assert isinstance(error, RuntimeError)
    # The message must be actionable: it names the service and the fix.
    assert "coding-test" in str(error)
    assert "construction" in str(error)


def test_guard_does_not_fire_at_construction_time() -> None:
    """False-positive control for the guard above.

    If ``_already_started`` were true straight after ``FastAPI()``, the guard
    would reject every legitimate call and this whole module would be unusable.
    Without this test, a broken guard still passes the test above.
    """
    from src.telemetry import _already_started

    assert _already_started(_app()) is False

    started = _app()
    with TestClient(started):
        pass
    assert _already_started(started) is True


# --------------------------------------------------------------------------
# Deliberate no-ops: quiet False, never a misleading True
# --------------------------------------------------------------------------


def test_no_endpoint_returns_false_and_app_still_serves() -> None:
    app = _app()
    assert setup_tracing(app, "coding-test") is False
    assert _drive(app) == 200


def test_blank_endpoint_is_treated_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTLP_TRACES_ENDPOINT", "   ")
    assert setup_tracing(_app(), "coding-test") is False


def test_sdk_disabled_wins_over_a_configured_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OTLP_TRACES_ENDPOINT", ENDPOINT)
    monkeypatch.setenv("OTEL_SDK_DISABLED", "TRUE")
    assert setup_tracing(_app(), "coding-test") is False


def test_missing_opentelemetry_packages_return_false_without_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A consumer that declares no OTEL packages must still start.

    coding-repo-jobs is in exactly this position.
    """
    monkeypatch.setenv("OTLP_TRACES_ENDPOINT", ENDPOINT)
    real_import = builtins.__import__

    def no_exporter(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("opentelemetry.exporter"):
            raise ImportError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_exporter)
    app = _app()
    assert setup_tracing(app, "coding-test") is False
    assert _drive(app) == 200


# --------------------------------------------------------------------------
# Probe exclusion — load-bearing for the 10Gi/14d Tempo PVC
# --------------------------------------------------------------------------


def test_health_is_excluded_but_api_is_not(collector: InMemorySpanExporter) -> None:
    """Both arms matter.

    The /health arm proves probes are dropped; the /api arm is the non-vacuity
    control — an excluded_urls pattern wide enough to swallow everything would
    pass the first assertion on its own.
    """
    app = _app()
    setup_tracing(app, "coding-test")

    assert _drive(app, "/health") == 200
    assert len(collector.get_finished_spans()) == 0, "probe traffic must not be traced"

    assert _drive(app, "/api/thing") == 200
    assert collector.get_finished_spans(), "real traffic must be traced"


def test_default_excluded_urls_covers_the_probe_paths_this_fleet_uses() -> None:
    for path in ("health", "metrics", "ready", "live"):
        assert path in DEFAULT_EXCLUDED_URLS


# --------------------------------------------------------------------------
# Credential hygiene
# --------------------------------------------------------------------------


def test_query_string_is_stripped_from_span_attributes(
    collector: InMemorySpanExporter,
) -> None:
    """A trace store must not become the second place a live token lands."""
    app = _app()
    setup_tracing(app, "coding-test")

    assert _drive(app, "/api/thing?token=SUPERSECRET&page=2") == 200

    blob = repr([dict(s.attributes or {}) for s in collector.get_finished_spans()])
    assert "SUPERSECRET" not in blob, blob
    # Non-vacuity: the URL attribute is still present and still useful.
    assert "/api/thing" in blob


def test_credential_headers_are_not_exported(collector: InMemorySpanExporter) -> None:
    app = _app()
    setup_tracing(app, "coding-test")

    assert (
        _drive(
            app,
            "/api/thing",
            headers={
                "Authorization": "Bearer lic_LIVE_TOKEN",
                "X-Tenant-Id": "0195f48b-0000-0000-0000-000000000001",
            },
        )
        == 200
    )

    blob = repr([dict(s.attributes or {}) for s in collector.get_finished_spans()])
    assert "lic_LIVE_TOKEN" not in blob
    assert "0195f48b-0000-0000-0000-000000000001" not in blob


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://h/api/thing?token=x", "http://h/api/thing"),
        ("http://h/api/thing", "http://h/api/thing"),
        ("http://h/api/thing?", "http://h/api/thing"),
        ("http://h/api/a?b=1?c=2", "http://h/api/a"),
    ],
)
def test_strip_query(raw: str, expected: str) -> None:
    assert _strip_query(raw) == expected


# --------------------------------------------------------------------------
# Client spans — without these the service is a graph node nothing points at
# --------------------------------------------------------------------------


@pytest.fixture
def _uninstrument_httpx():
    """httpx instrumentation is a process-wide singleton; isolate it on both sides.

    Cleaning up only afterwards is not enough: any earlier test that called
    ``setup_tracing`` left httpx instrumented against *its* provider, and the
    idempotence guard then short-circuited, so this test saw zero spans and the
    assertion failed for a reason that had nothing to do with the code.
    """
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    HTTPXClientInstrumentor().uninstrument()
    yield
    HTTPXClientInstrumentor().uninstrument()


@pytest.fixture
def local_server():
    """A real HTTP server on a real socket.

    ``httpx.MockTransport`` is deliberately NOT used here: the instrumentation
    patches ``httpx.HTTPTransport.handle_request``, so a mock transport bypasses
    the exact code under test and yields zero spans whether the SDK instruments
    httpx or not. That first draft of this test failed for that reason, which is
    the only way it surfaced.
    """
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib interface
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/api/x"
    finally:
        server.shutdown()
        server.server_close()


def _client_span_kinds(collector: InMemorySpanExporter) -> list[str]:
    return [str(s.kind) for s in collector.get_finished_spans() if "CLIENT" in str(s.kind)]


def test_outbound_httpx_calls_produce_client_spans(
    collector: InMemorySpanExporter,
    local_server: str,
    _uninstrument_httpx: None,
) -> None:
    """Tempo's service_graphs processor builds edges from CLIENT spans.

    A service with server spans only appears in the graph as a node nothing
    points at, so this is what makes the coding call graph legible rather than a
    list of unconnected boxes.
    """
    import httpx

    assert setup_tracing(_app(), "coding-test") is True

    with httpx.Client() as client:
        assert client.get(local_server).status_code == 200

    assert _client_span_kinds(collector), (
        "no client span produced — the service graph will have no outgoing edge"
    )


def test_httpx_rebinds_when_something_already_instrumented_it(
    collector: InMemorySpanExporter,
    local_server: str,
    _uninstrument_httpx: None,
) -> None:
    """``HTTPXClientInstrumentor`` is a process-wide singleton that binds its
    tracer at ``instrument()`` time.

    So if anything instrumented httpx earlier — another library, a plugin, a
    previous ``setup_tracing`` in the same process — an idempotence guard that
    simply returns leaves client spans going to *that* provider, and this
    service's outgoing service-graph edges silently vanish. Reproduced exactly
    that way in this suite before the rebind was added.
    """
    import httpx
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    foreign_exporter = InMemorySpanExporter()
    foreign = TracerProvider()
    # Deliberately not foreign.add_span_processor(...): the collector fixture has
    # patched that class-wide, which would route these spans to the collector and
    # make the assertion below unfalsifiable.
    _REAL_ADD_SPAN_PROCESSOR(foreign, SimpleSpanProcessor(foreign_exporter))
    HTTPXClientInstrumentor().instrument(tracer_provider=foreign)

    assert setup_tracing(_app(), "coding-test") is True

    with httpx.Client() as client:
        assert client.get(local_server).status_code == 200

    assert _client_span_kinds(collector), (
        "client spans went to the pre-existing provider — setup_tracing did not rebind httpx"
    )
    assert len(foreign_exporter.get_finished_spans()) == 0, (
        "client spans still reaching the foreign provider"
    )


def test_httpx_binds_to_our_provider_even_if_the_global_is_already_taken(
    collector: InMemorySpanExporter,
    local_server: str,
    _uninstrument_httpx: None,
) -> None:
    """``set_tracer_provider`` is set-once: a global claimed earlier stays claimed.

    In that process our own ``set_tracer_provider`` call is ignored, so anything
    that resolves the *global* — including an httpx instrumentation bound without
    an explicit provider — exports to someone else's pipeline instead of ours.
    Binding httpx explicitly is what makes this service's client spans survive
    that, and it is the difference this test exists to hold.
    """
    import httpx
    from opentelemetry import trace

    foreign_exporter = InMemorySpanExporter()
    foreign = TracerProvider()
    _REAL_ADD_SPAN_PROCESSOR(foreign, SimpleSpanProcessor(foreign_exporter))
    trace.set_tracer_provider(foreign)  # claims the global before we run

    assert setup_tracing(_app(), "coding-test") is True

    with httpx.Client() as client:
        assert client.get(local_server).status_code == 200

    assert _client_span_kinds(collector), (
        "client spans went to the provider that already held the global — httpx was "
        "bound implicitly instead of to this service's provider"
    )


def test_httpx_instrumentation_can_be_declined(
    collector: InMemorySpanExporter,
    local_server: str,
    _uninstrument_httpx: None,
) -> None:
    """False-positive control for the test above.

    Without this, an implementation that instruments httpx unconditionally would
    pass the previous test while ignoring the flag entirely.
    """
    import httpx

    assert setup_tracing(_app(), "coding-test", instrument_httpx=False) is True

    with httpx.Client() as client:
        assert client.get(local_server).status_code == 200

    assert _client_span_kinds(collector) == []


# --------------------------------------------------------------------------
# The campaign's own use case
# --------------------------------------------------------------------------


def test_auth_denied_requests_are_still_traced(collector: InMemorySpanExporter) -> None:
    """401s are the events this fleet most needs to see.

    Measured both orderings: instrument_app wraps at the ASGI layer, outside the
    user middleware stack, so a middleware that short-circuits every request
    still yields a span either way.
    """
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    class DenyAll(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):  # noqa: ANN001, ANN202
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

    app = _app()
    app.add_middleware(DenyAll)
    setup_tracing(app, "coding-test")

    assert _drive(app) == 401
    spans = collector.get_finished_spans()
    assert spans, "an auth-denied request produced no span"
    assert any((s.attributes or {}).get("http.status_code") == 401 for s in spans)
