"""On-behalf-of vouching: an allowlisted service may act for another tenant.

The shape under test, and why each half matters:

* A service presents its **own** license and names a **customer** tenant in a
  plain ``X-Tenant-Id``. Honoured only when the license's ``subject_id`` is in
  ``CODING_ONBEHALF_SUBJECTS``.
* An **unvouched** disagreement is a **403** — not a silent downgrade to the
  caller's own tenant, which would hide an authorisation failure behind a 200 and
  serve the wrong data.
* An **agreeing** header is a no-op, because coding-gateway re-injects the tenant
  it resolved from the same token on every north-south request. Getting this
  wrong 403s the entire browser-facing path.

Test-double discipline follows the file next door: patch
``coding_client.auth.tenant.httpx.AsyncClient`` rather than
``_introspect_license``, so the real introspection path and its caches run.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from coding_client.auth import _default_tenant as dt_mod
from coding_client.auth import _onbehalf as ob_mod
from coding_client.auth import _trusted_networks as tn_mod
from coding_client.auth.middleware import AuthMiddleware
from coding_client.auth.tenant import (
    TenantMiddleware,
    clear_license_caches,
    optional_tenant,
    require_tenant,
)
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient as FastAPITestClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

SERVICE_SUBJECT = "019f2a06-6f0d-75c6-8409-0e9dc07ddda4"
OTHER_SUBJECT = "019f2a06-98d8-7460-b2d3-d7edff039bf8"
SERVICE_TENANT = "service-own-tenant-0001"
CUSTOMER_TENANT = "customer-tenant-0042"
INTROSPECT_URL = "http://test-licenses/license/introspect"


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """Every other identity source off, so a 200 can only be the vouch."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("SKIP_AUTH", raising=False)
    monkeypatch.delenv("DEV_API_KEY", raising=False)
    monkeypatch.delenv("TEST_API_KEY", raising=False)
    monkeypatch.delenv("CODING_ONBEHALF_SUBJECTS", raising=False)
    # The gate is OFF throughout: vouching only matters once the header is no
    # longer trusted outright. With it on, the header branch mints the user and
    # none of this code is reached.
    monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
    monkeypatch.setenv("LICENSE_INTROSPECT_URL", INTROSPECT_URL)
    monkeypatch.setattr(tn_mod, "TRUSTED_NETWORKS", [])
    monkeypatch.setattr(dt_mod, "DEFAULT_TENANT_ID", None)
    # The once-only log guard is module state; a stale entry would silence the
    # ERROR a later test asserts on.
    ob_mod._warned_synthetic.clear()
    clear_license_caches()
    yield
    ob_mod._warned_synthetic.clear()
    clear_license_caches()


def _introspection(payload: dict | None, *, status_code: int = 200):
    """Fake the HTTP endpoint, not the function — see the module docstring."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return patch("coding_client.auth.tenant.httpx.AsyncClient", return_value=client), client


def _service_license(subject: str | None = SERVICE_SUBJECT) -> dict:
    body: dict = {"active": True, "tenant_id": SERVICE_TENANT}
    if subject is not None:
        body["subject_id"] = subject
    return body


def _whoami(request: Request) -> JSONResponse:
    user = getattr(request.state, "user", None)
    if user is None:
        # Distinct from a 401 so a sloppy assertion cannot conflate them.
        return JSONResponse({"error": "no user on request.state"}, status_code=500)
    return JSONResponse(
        {
            "sub": user.sub,
            "tenant_id": user.tenant_id,
            "effective_tenant_id": user.effective_tenant_id,
            "vouching_subject_id": getattr(request.state, "vouching_subject_id", None),
            "license_id": getattr(request.state, "license_id", None),
            # Reported as a tri-state on purpose: `None` means the resolver never
            # ran at all, which is a different failure from "ran and said no".
            "tenant_vouched": getattr(request.state, "tenant_vouched", None),
        }
    )


def _client() -> TestClient:
    app = Starlette(routes=[Route("/api/test", _whoami)])
    app.add_middleware(AuthMiddleware)
    return TestClient(app, raise_server_exceptions=False)


def _bare_request(headers: dict[str, str], host: str = "10.42.0.17"):
    request = MagicMock()
    request.state = type("State", (), {})()
    request.headers = headers
    request.client = MagicMock()
    request.client.host = host
    request.url.path = "/api/test"
    return request


# ---------------------------------------------------------------------------
# AuthMiddleware
# ---------------------------------------------------------------------------
class TestMiddlewareVouching:
    def test_allowlisted_subject_may_act_for_another_tenant(self, monkeypatch):
        """The whole point: the response is scoped to the CUSTOMER, not the service."""
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", SERVICE_SUBJECT)
        introspect, _ = _introspection(_service_license())
        with introspect:
            resp = _client().get(
                "/api/test",
                headers={
                    "Authorization": "Bearer service-license",
                    "X-Tenant-Id": CUSTOMER_TENANT,
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["tenant_id"] == CUSTOMER_TENANT
        assert body["effective_tenant_id"] == CUSTOMER_TENANT
        # The service's own tenant must not leak into the scoped identity.
        assert SERVICE_TENANT not in resp.text
        # ...but it must remain attributable to the subject that vouched.
        assert body["vouching_subject_id"] == SERVICE_SUBJECT

    def test_a_non_allowlisted_subject_is_refused(self, monkeypatch):
        """An active, verified license is still not permission to speak for others."""
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", OTHER_SUBJECT)
        introspect, _ = _introspection(_service_license())
        with introspect:
            resp = _client().get(
                "/api/test",
                headers={
                    "Authorization": "Bearer service-license",
                    "X-Tenant-Id": CUSTOMER_TENANT,
                },
            )

        assert resp.status_code == 403
        assert resp.json()["error"] == "TENANT_ASSERTION_NOT_PERMITTED"
        assert CUSTOMER_TENANT not in resp.text

    def test_an_empty_allowlist_refuses(self):
        """Unset vouches for nobody. This is what makes the feature inert on install."""
        introspect, _ = _introspection(_service_license())
        with introspect:
            resp = _client().get(
                "/api/test",
                headers={
                    "Authorization": "Bearer service-license",
                    "X-Tenant-Id": CUSTOMER_TENANT,
                },
            )

        assert resp.status_code == 403

    def test_403_not_401_because_the_caller_is_authenticated(self, monkeypatch):
        """The distinction is the point: retrying with other credentials is not the fix."""
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", OTHER_SUBJECT)
        introspect, _ = _introspection(_service_license())
        with introspect:
            resp = _client().get(
                "/api/test",
                headers={
                    "Authorization": "Bearer service-license",
                    "X-Tenant-Id": CUSTOMER_TENANT,
                },
            )
        assert resp.status_code == 403
        assert resp.status_code != 401

    def test_an_agreeing_header_is_not_an_assertion(self, monkeypatch):
        """coding-gateway re-injects the tenant it resolved from this same token.

        Every north-south request carries both headers. If this goes red the
        browser-facing path 403s the moment the gateway is flipped.
        """
        introspect, _ = _introspection(_service_license())
        with introspect:
            resp = _client().get(
                "/api/test",
                headers={
                    "Authorization": "Bearer service-license",
                    "X-Tenant-Id": SERVICE_TENANT,
                },
            )

        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == SERVICE_TENANT

    def test_an_agreeing_header_differing_only_in_case_is_not_an_assertion(self):
        introspect, _ = _introspection(_service_license())
        with introspect:
            resp = _client().get(
                "/api/test",
                headers={
                    "Authorization": "Bearer service-license",
                    "X-Tenant-Id": SERVICE_TENANT.upper(),
                },
            )
        assert resp.status_code == 200

    def test_no_header_is_unchanged_behaviour(self):
        """The inertness claim, at the middleware."""
        introspect, _ = _introspection(_service_license())
        with introspect:
            resp = _client().get("/api/test", headers={"Authorization": "Bearer service-license"})

        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == SERVICE_TENANT
        assert resp.json()["vouching_subject_id"] is None

    @pytest.mark.parametrize(
        "smuggled",
        ["Bearer some-token", "bearer some-token", "Bearer  some-token", "Bearer\tsome-token"],
    )
    def test_a_bearer_shaped_tenant_header_is_not_a_tenant(self, monkeypatch, smuggled):
        """Some fleet clients overload X-Tenant-Id to carry a credential.

        Binding a tenant literally named "Bearer" would be a smuggling path, and
        a plain ``startswith("Bearer ")`` test misses the whitespace variants.
        """
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", SERVICE_SUBJECT)
        introspect, _ = _introspection(_service_license())
        with introspect:
            resp = _client().get(
                "/api/test",
                headers={"Authorization": "Bearer service-license", "X-Tenant-Id": smuggled},
            )

        # Treated as absent: the token's own tenant, no vouch, no 403.
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == SERVICE_TENANT
        assert resp.json()["vouching_subject_id"] is None

    def test_a_whitespace_only_assertion_is_absent_not_a_disagreement(self):
        introspect, _ = _introspection(_service_license())
        with introspect:
            resp = _client().get(
                "/api/test",
                headers={"Authorization": "Bearer service-license", "X-Tenant-Id": "   "},
            )
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == SERVICE_TENANT

    def test_an_inactive_license_cannot_vouch(self, monkeypatch):
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", SERVICE_SUBJECT)
        introspect, _ = _introspection({"active": False, "reason": "token_invalid"})
        with introspect:
            resp = _client().get(
                "/api/test",
                headers={
                    "Authorization": "Bearer revoked",
                    "X-Tenant-Id": CUSTOMER_TENANT,
                },
            )

        # No verified identity at all, so this never reaches the vouch: 401.
        assert resp.status_code == 401
        assert CUSTOMER_TENANT not in resp.text

    def test_the_synthetic_subject_marker_can_never_vouch(self, monkeypatch):
        """`license:<tenant>` is shared by every subject-less license for a tenant.

        Allowlisting it would hand the vouch to all of them at once, so it is
        rejected at parse time even when an operator writes it in.
        """
        introspect, _ = _introspection(_service_license(subject=None))
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", f"license:{SERVICE_TENANT}")
        with introspect:
            resp = _client().get(
                "/api/test",
                headers={
                    "Authorization": "Bearer service-license",
                    "X-Tenant-Id": CUSTOMER_TENANT,
                },
            )

        assert resp.status_code == 403
        assert CUSTOMER_TENANT not in resp.text

    def test_forwarded_license_id_is_captured_for_attribution(self, monkeypatch):
        """The CUSTOMER's license is what should be billed, not the voucher's."""
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", SERVICE_SUBJECT)
        customer_license = "019ff6c4-bff2-76a8-8fb4-fefd2ca9bdc1"
        introspect, _ = _introspection(_service_license())
        with introspect:
            resp = _client().get(
                "/api/test",
                headers={
                    "Authorization": "Bearer service-license",
                    "X-Tenant-Id": CUSTOMER_TENANT,
                    "X-License-Id": customer_license,
                },
            )

        assert resp.status_code == 200
        assert resp.json()["license_id"] == customer_license

    def test_a_malformed_forwarded_license_id_is_dropped_not_echoed(self, monkeypatch):
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", SERVICE_SUBJECT)
        introspect, _ = _introspection(_service_license())
        with introspect:
            resp = _client().get(
                "/api/test",
                headers={
                    "Authorization": "Bearer service-license",
                    "X-Tenant-Id": CUSTOMER_TENANT,
                    "X-License-Id": "'; DROP TABLE licenses; --",
                },
            )

        assert resp.status_code == 200
        assert resp.json()["license_id"] is None
        assert "DROP TABLE" not in resp.text


# ---------------------------------------------------------------------------
# require_tenant / optional_tenant — the same rule, one layer down
# ---------------------------------------------------------------------------
class TestDependencyVouching:
    async def test_require_tenant_honours_a_vouched_assertion(self, monkeypatch):
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", SERVICE_SUBJECT)
        request = _bare_request(
            {"Authorization": "Bearer service-license", "x-tenant-id": CUSTOMER_TENANT}
        )
        introspect, _ = _introspection(_service_license())
        with introspect:
            assert await require_tenant(request) == CUSTOMER_TENANT

    async def test_require_tenant_refuses_an_unvouched_assertion(self):
        from fastapi import HTTPException

        request = _bare_request(
            {"Authorization": "Bearer service-license", "x-tenant-id": CUSTOMER_TENANT}
        )
        introspect, _ = _introspection(_service_license())
        with introspect, pytest.raises(HTTPException) as exc:
            await require_tenant(request)

        assert exc.value.status_code == 403

    async def test_optional_tenant_refuses_rather_than_returning_none(self):
        """A denial must not be reinterpreted as "no tenant context".

        Returning None here would let a pass-through route continue on a
        default; returning the caller's own tenant would scope the customer's
        request to the service. Both turn a refusal into something else.
        """
        from fastapi import HTTPException

        request = _bare_request(
            {"Authorization": "Bearer service-license", "x-tenant-id": CUSTOMER_TENANT}
        )
        introspect, _ = _introspection(_service_license())
        with introspect, pytest.raises(HTTPException) as exc:
            await optional_tenant(request)

        assert exc.value.status_code == 403

    async def test_optional_tenant_honours_a_vouched_assertion(self, monkeypatch):
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", SERVICE_SUBJECT)
        request = _bare_request(
            {"Authorization": "Bearer service-license", "x-tenant-id": CUSTOMER_TENANT}
        )
        introspect, _ = _introspection(_service_license())
        with introspect:
            assert await optional_tenant(request) == CUSTOMER_TENANT

    async def test_the_bearer_scheme_is_case_insensitive_here_too(self, monkeypatch):
        """These used to disagree with AuthMiddleware.

        A lowercase `bearer` authenticated through the middleware and was
        invisible to this dependency, so a route using it 401'd a request the
        middleware had just admitted.
        """
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", SERVICE_SUBJECT)
        request = _bare_request(
            {"Authorization": "bearer service-license", "x-tenant-id": CUSTOMER_TENANT}
        )
        introspect, _ = _introspection(_service_license())
        with introspect:
            assert await require_tenant(request) == CUSTOMER_TENANT


# ---------------------------------------------------------------------------
# The full stack, as a service actually runs it
# ---------------------------------------------------------------------------
def _full_stack_app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/whoami")
    async def whoami(tenant_id: str = Depends(require_tenant)):
        return {"tenant_id": tenant_id}

    app.add_middleware(TenantMiddleware)
    app.add_middleware(AuthMiddleware)
    return app


class TestFullStackAgreement:
    def test_middleware_and_dependency_agree_on_a_vouched_call(self, monkeypatch):
        """Both layers resolve the customer, not the service.

        If only one had the arm, the middleware would scope the user one way and
        the route dependency another — the drift that made TRUSTED_CIDRS
        permissive in one file after it was fixed in the other.
        """
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", SERVICE_SUBJECT)
        introspect, _ = _introspection(_service_license())
        with introspect:
            resp = FastAPITestClient(_full_stack_app()).get(
                "/api/whoami",
                headers={
                    "Authorization": "Bearer service-license",
                    "X-Tenant-Id": CUSTOMER_TENANT,
                },
            )

        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == CUSTOMER_TENANT

    def test_full_stack_refuses_an_unvouched_assertion(self):
        introspect, _ = _introspection(_service_license())
        with introspect:
            resp = FastAPITestClient(_full_stack_app()).get(
                "/api/whoami",
                headers={
                    "Authorization": "Bearer service-license",
                    "X-Tenant-Id": CUSTOMER_TENANT,
                },
            )

        assert resp.status_code == 403
        assert CUSTOMER_TENANT not in resp.text


# ---------------------------------------------------------------------------
# The decision records itself, so a downstream hop can act on it
# ---------------------------------------------------------------------------
def _ws_with_real_state(headers: dict[str, str]):
    """A WebSocket stand-in whose ``.state`` is a REAL object.

    ``MagicMock().state.tenant_vouched`` is truthy for every attribute that was
    never set, so a `MagicMock` here would make every assertion below pass
    regardless of what the code does. The WS harness next door can use a plain
    MagicMock because it only ever reads ``.headers`` / ``.url``; these tests
    read back what the resolver WROTE, so the state has to be real.
    """
    ws = MagicMock()
    ws.headers = {k.lower(): v for k, v in headers.items()}
    ws.url.path = "/api/quality/ws/c1"
    ws.state = type("State", (), {})()
    return ws


class TestTheVouchRecordsItself:
    """`coding-gateway` forwards the caller's credential when the tenant agreed
    and substitutes its own when it had to vouch. It cannot re-derive which
    happened, so the decision is recorded on ``request.state``. These pin the
    flag to the *branch*, not merely to its existence.
    """

    async def test_a_vouched_call_records_the_vouch_and_who_made_it(self, monkeypatch):
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", SERVICE_SUBJECT)
        request = _bare_request(
            {"Authorization": "Bearer service-license", "x-tenant-id": CUSTOMER_TENANT}
        )
        introspect, _ = _introspection(_service_license())
        with introspect:
            assert await require_tenant(request) == CUSTOMER_TENANT

        assert request.state.tenant_vouched is True
        assert request.state.asserted_tenant == CUSTOMER_TENANT
        assert request.state.vouching_subject_id == SERVICE_SUBJECT

    async def test_an_agreeing_header_is_recorded_as_not_vouched(self, monkeypatch):
        """The mutant this exists to kill: substituting the credential always.

        coding-gateway re-injects the tenant it resolved from the very same
        token on every north-south request, so `asserted == token` is the common
        case, not the exception. If it were flagged as a vouch, the gateway would
        replace the customer's own credential on ordinary browser traffic and
        every customer's spend would bill to the gateway.
        """
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", SERVICE_SUBJECT)
        request = _bare_request(
            {"Authorization": "Bearer service-license", "x-tenant-id": SERVICE_TENANT}
        )
        introspect, _ = _introspection(_service_license())
        with introspect:
            assert await require_tenant(request) == SERVICE_TENANT

        assert request.state.tenant_vouched is False

    async def test_no_asserted_header_is_recorded_as_not_vouched(self, monkeypatch):
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", SERVICE_SUBJECT)
        request = _bare_request({"Authorization": "Bearer service-license"})
        introspect, _ = _introspection(_service_license())
        with introspect:
            assert await require_tenant(request) == SERVICE_TENANT

        assert request.state.tenant_vouched is False

    async def test_a_refused_assertion_is_recorded_as_not_vouched(self):
        """A refusal must never read back as a vouch.

        The refusal path also computes `asserted`, so a flag set before the
        allowlist check — rather than on the honoured branch — would mark the
        exact request that was just denied as vouched.
        """
        from fastapi import HTTPException

        request = _bare_request(
            {"Authorization": "Bearer service-license", "x-tenant-id": CUSTOMER_TENANT}
        )
        introspect, _ = _introspection(_service_license())
        with introspect, pytest.raises(HTTPException) as exc:
            await require_tenant(request)

        assert exc.value.status_code == 403
        assert request.state.tenant_vouched is False

    async def test_optional_tenant_records_it_too(self, monkeypatch):
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", SERVICE_SUBJECT)
        request = _bare_request(
            {"Authorization": "Bearer service-license", "x-tenant-id": CUSTOMER_TENANT}
        )
        introspect, _ = _introspection(_service_license())
        with introspect:
            assert await optional_tenant(request) == CUSTOMER_TENANT

        assert request.state.tenant_vouched is True

    def test_the_middleware_records_it_too(self, monkeypatch):
        """All three resolvers, or the gateway's HTTP and WS paths disagree."""
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", SERVICE_SUBJECT)
        introspect, _ = _introspection(_service_license())
        with introspect:
            resp = _client().get(
                "/api/test",
                headers={
                    "Authorization": "Bearer service-license",
                    "X-Tenant-Id": CUSTOMER_TENANT,
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["tenant_vouched"] is True
        assert body["effective_tenant_id"] == CUSTOMER_TENANT

    async def test_a_websocket_scope_records_the_same_state_a_request_does(self, monkeypatch):
        """The gateway resolves WS upgrades through this same code.

        `AuthMiddleware` is a BaseHTTPMiddleware and never runs on a websocket
        scope, so if the flag were set anywhere but in the shared decision
        function, every WebSocket would read back as un-vouched and the gateway
        would forward a credential naming the wrong tenant.
        """
        from coding_client.auth.websocket import Outcome, resolve_websocket_identity

        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", SERVICE_SUBJECT)
        ws = _ws_with_real_state(
            {"authorization": "Bearer service-license", "x-tenant-id": CUSTOMER_TENANT}
        )
        introspect, _ = _introspection(_service_license())
        with introspect:
            ident = await resolve_websocket_identity(ws)

        assert ident.outcome is Outcome.RESOLVED
        assert ws.state.tenant_vouched is True
        assert ws.state.asserted_tenant == CUSTOMER_TENANT

    async def test_the_customer_license_is_recorded_not_the_vouching_services(self, monkeypatch):
        """Attribution rides the caller's forwarded X-License-Id.

        Taking it from the vouching service's own introspection body would bill
        every customer's spend to that service. The two are deliberately
        different values here so a mutant that reads the wrong one cannot pass.
        """
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", SERVICE_SUBJECT)
        customer_license = "3f7a1c0e-0000-4000-8000-00000000c0de"
        service_license = "11111111-2222-4333-8444-555555555555"
        request = _bare_request(
            {
                "Authorization": "Bearer service-license",
                "x-tenant-id": CUSTOMER_TENANT,
                "x-license-id": customer_license,
            }
        )
        body = _service_license()
        body["license_id"] = service_license
        introspect, _ = _introspection(body)
        with introspect:
            assert await require_tenant(request) == CUSTOMER_TENANT

        assert request.state.license_id == customer_license
        assert request.state.license_id != service_license

    async def test_license_verified_is_true_only_after_the_licence_arm_ran(self, monkeypatch):
        """The question a service must ask before lending its own credential.

        Driven live on 2026-08-14: a forged, credential-less x-tenant-id on a
        WebSocket upgrade was accepted by coding-gateway under header trust, the
        gateway attached its OWN allowlisted licence, and coding-analysis logged
        a real `Vouched on-behalf-of` for a tenant nobody had verified. Any pod
        could read any tenant. `tenant_was_vouched` alone cannot prevent that —
        it is False in both "resolved from a licence, tenants agreed" and "never
        resolved at all", and those two must lead to opposite outbound decisions.
        """
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", SERVICE_SUBJECT)
        request = _bare_request(
            {"Authorization": "Bearer service-license", "x-tenant-id": CUSTOMER_TENANT}
        )
        introspect, _ = _introspection(_service_license())
        with introspect:
            await require_tenant(request)

        assert ob_mod.tenant_license_verified(request) is True

    async def test_license_verified_is_true_even_when_the_tenants_agreed(self, monkeypatch):
        """Verified is about the SOURCE, not the outcome.

        An agreeing header is still a licence-resolved tenant, and the caller's
        own credential is safe to forward. Conflating this with "not vouched"
        would strip the credential off ordinary north-south traffic.
        """
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", SERVICE_SUBJECT)
        request = _bare_request(
            {"Authorization": "Bearer service-license", "x-tenant-id": SERVICE_TENANT}
        )
        introspect, _ = _introspection(_service_license())
        with introspect:
            await require_tenant(request)

        assert ob_mod.tenant_license_verified(request) is True
        assert ob_mod.tenant_was_vouched(request) is False

    async def test_license_verified_is_false_for_a_trusted_header(self, monkeypatch):
        """THE hole. A tenant nobody verified must never earn our credential."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "true")
        request = _bare_request({"x-tenant-id": CUSTOMER_TENANT})
        assert await require_tenant(request) == CUSTOMER_TENANT

        assert ob_mod.tenant_license_verified(request) is False
        assert ob_mod.tenant_was_vouched(request) is False

    async def test_license_verified_is_false_for_a_refused_assertion(self):
        """A refusal resolved nothing; it must not read as verified either."""
        from fastapi import HTTPException

        request = _bare_request(
            {"Authorization": "Bearer service-license", "x-tenant-id": CUSTOMER_TENANT}
        )
        introspect, _ = _introspection(_service_license())
        with introspect, pytest.raises(HTTPException):
            await require_tenant(request)

        # The arm DID run, so this is True — and that is correct: the caller is
        # authenticated. The refusal is carried by the 403, not by this flag.
        assert ob_mod.tenant_license_verified(request) is True
        assert ob_mod.tenant_was_vouched(request) is False

    def test_license_verified_is_false_when_nothing_ran(self):
        request = _bare_request({})
        assert ob_mod.tenant_license_verified(request) is False

    def test_tenant_was_vouched_is_false_when_the_resolver_never_ran(self):
        """The accessor's default is the safe answer, and it is REACHABLE.

        Header-trust, trusted-network and no-credential requests never reach the
        decision function at all, so the gateway asks this question about
        requests that carry no recorded answer. It must say "no vouch", not
        raise and not guess.
        """
        request = _bare_request({})
        assert ob_mod.tenant_was_vouched(request) is False

    async def test_tenant_was_vouched_reads_what_the_resolver_wrote(self, monkeypatch):
        """Non-vacuity control for the test above: the accessor can return True.

        Without this, `tenant_was_vouched` could be `return False` and every
        other assertion in this class would still pass.
        """
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", SERVICE_SUBJECT)
        request = _bare_request(
            {"Authorization": "Bearer service-license", "x-tenant-id": CUSTOMER_TENANT}
        )
        introspect, _ = _introspection(_service_license())
        with introspect:
            await require_tenant(request)

        assert ob_mod.tenant_was_vouched(request) is True


# ---------------------------------------------------------------------------
# The allowlist parser
# ---------------------------------------------------------------------------
class TestAllowlistParsing:
    def test_unset_is_empty(self):
        assert ob_mod.onbehalf_subjects() == frozenset()

    def test_blank_and_trailing_commas_are_tolerated(self, monkeypatch):
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", f" {SERVICE_SUBJECT} , ,{OTHER_SUBJECT},")
        assert ob_mod.onbehalf_subjects() == frozenset({SERVICE_SUBJECT, OTHER_SUBJECT})

    def test_a_synthetic_marker_entry_is_dropped_and_logged(self, monkeypatch, caplog):
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", f"license:some-tenant,{SERVICE_SUBJECT}")
        with caplog.at_level("ERROR", logger="coding_client.auth._onbehalf"):
            subjects = ob_mod.onbehalf_subjects()

        assert subjects == frozenset({SERVICE_SUBJECT})
        # getMessage() interpolates the args once; `r.message % r.args` would
        # double-format and raise.
        assert any("synthetic marker" in r.getMessage() for r in caplog.records)

    def test_may_vouch_is_false_for_every_missing_input(self, monkeypatch):
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", SERVICE_SUBJECT)
        assert ob_mod.may_vouch(None) is False
        assert ob_mod.may_vouch("") is False
        assert ob_mod.may_vouch(OTHER_SUBJECT) is False
        assert ob_mod.may_vouch(f"license:{SERVICE_TENANT}") is False
        assert ob_mod.may_vouch(SERVICE_SUBJECT) is True

    def test_the_marker_is_refused_even_if_it_reaches_the_allowlist(self, monkeypatch):
        """The second of two independent layers, pinned on its own.

        :func:`onbehalf_subjects` already drops ``license:`` entries, so in
        normal operation the marker can never be *in* the parsed set and the
        check inside :func:`may_vouch` is unreachable. That redundancy is
        deliberate — an auth boundary should not depend on a single guard — but
        it also means a mutation of either layer survives while the other holds,
        and an unpinned guard is one refactor away from being deleted as dead
        code.

        Bypassing the parser is the only way to exercise the inner layer as the
        independent check it is.
        """
        marker = f"license:{SERVICE_TENANT}"
        monkeypatch.setattr(ob_mod, "onbehalf_subjects", lambda: frozenset({marker}))

        # Control: the fake allowlist really is in force, so a False below
        # cannot be "the allowlist was empty all along".
        assert ob_mod.may_vouch("any-other-subject") is False
        assert marker in ob_mod.onbehalf_subjects()

        assert ob_mod.may_vouch(marker) is False

    def test_there_is_no_wildcard_spelling(self, monkeypatch):
        """A permissive escape hatch would re-create the confused deputy."""
        for wildcard in ("*", "all", "any", "ALL"):
            monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", wildcard)
            assert ob_mod.may_vouch(SERVICE_SUBJECT) is False
