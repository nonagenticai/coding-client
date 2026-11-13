"""TRUST_TENANT_HEADER: gating trust in unverified X-Tenant-Id headers.

The vector these tests pin down
-------------------------------
``require_tenant`` resolves the tenant from a bare ``X-Tenant-Id`` request
header (Priority 1b) *before* it ever tries license introspection (Priority 2).
The header is not verified by anything in this library. At the mesh edge that is
fine — ``ext-authz-enforce.yaml`` strips whatever the client sent and re-injects
the tenant that ``license-authz`` resolved from a real license. Pod-to-pod it is
not fine: in-cluster callers never traverse that filter, so any workload that can
open a socket to a ``coding-*`` port can claim any tenant and be served it.

Emptying ``TRUSTED_CIDRS`` (done in 1.7.0) does not close this. That knob only
governs the case where the request carries *no* header at all; a forged header
returns at Priority 1b and never reaches the network check.

What is asserted here
---------------------
* With the gate OFF, a forged header and no valid license produces a **401** —
  asserted on the outcome of the request, not on the fact that a flag was read.
* With the gate OFF and a valid license present, the tenant comes from the
  **license**, and the forged header loses. This is the "falls through, is not
  silently downgraded to DEFAULT_TENANT_ID" contract.
* With the gate UNSET, the forged header is still honoured. That is the
  compatibility guarantee the per-service rollout depends on — if this test ever
  goes red, merging the library broke live traffic.
"""

from __future__ import annotations

import ipaddress
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from coding_client.auth import _default_tenant as dt_mod
from coding_client.auth import _trusted_networks as tn_mod
from coding_client.auth._header_trust import trust_tenant_header
from coding_client.auth.middleware import AuthMiddleware
from coding_client.auth.tenant import (
    TenantMiddleware,
    clear_license_caches,
    create_tenant_context,
    get_current_user_with_tenant,
    optional_tenant,
    require_tenant,
)
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

VICTIM_TENANT = "victim-tenant-0007"
LICENSE_TENANT = "licensed-tenant-0001"
# A tenant an operator actually configured, as DEFAULT_TENANT_ID would be in a
# Deployment. Since 1.9.0 there is no built-in literal to fall back on, so any
# test exercising the trusted-network bypass has to name one.
CONFIGURED_TENANT = "configured-tenant-0042"


@pytest.fixture(autouse=True)
def _isolate_auth_env(monkeypatch):
    """Neutralise every *other* way a tenant could be resolved.

    Without this an assertion could pass for the wrong reason — SKIP_AUTH
    returning "test-tenant", or the trusted-network bypass handing out
    DEFAULT_TENANT_ID — and we would be testing nothing.
    """
    monkeypatch.delenv("SKIP_AUTH", raising=False)
    monkeypatch.delenv("TRUST_TENANT_HEADER", raising=False)
    # Vouching off unless a test opts in — otherwise an inherited allowlist
    # would honour an asserted tenant and the forgery assertions here would pass
    # for the wrong reason.
    monkeypatch.delenv("CODING_ONBEHALF_SUBJECTS", raising=False)
    monkeypatch.setenv("LICENSE_INTROSPECT_URL", "http://test-licenses/license/introspect")
    monkeypatch.setattr(tn_mod, "TRUSTED_NETWORKS", [])
    # BOTH introspection caches — a refused token cached by one test would
    # otherwise suppress the next test's outbound call.
    clear_license_caches()


def _bare_request(headers: dict[str, str], host: str = "10.42.0.17"):
    """A request with no middleware-populated state, from a pod IP."""
    request = MagicMock()
    request.state = type("State", (), {})()
    request.headers = headers
    request.client = MagicMock()
    request.client.host = host
    return request


def _mock_license(tenant_id: str, active: bool = True):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"active": active, "tenant_id": tenant_id}
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return patch("coding_client.auth.tenant.httpx.AsyncClient", return_value=client)


# ---------------------------------------------------------------------------
# The knob itself
# ---------------------------------------------------------------------------
class TestTrustTenantHeaderKnob:
    def test_defaults_to_trusting_when_unset(self, monkeypatch):
        """The default is deliberately the insecure-but-compatible one."""
        monkeypatch.delenv("TRUST_TENANT_HEADER", raising=False)
        assert trust_tenant_header() is True

    @pytest.mark.parametrize("value", ["false", "False", "FALSE", " false ", "0", "no", "off"])
    def test_disable_values(self, monkeypatch, value):
        monkeypatch.setenv("TRUST_TENANT_HEADER", value)
        assert trust_tenant_header() is False

    @pytest.mark.parametrize("value", ["true", "True", "1", "yes", "on"])
    def test_enable_values(self, monkeypatch, value):
        monkeypatch.setenv("TRUST_TENANT_HEADER", value)
        assert trust_tenant_header() is True

    def test_empty_string_is_treated_as_unset(self, monkeypatch):
        monkeypatch.setenv("TRUST_TENANT_HEADER", "")
        assert trust_tenant_header() is True

    def test_unrecognised_value_keeps_the_default_and_logs(self, monkeypatch, caplog):
        """A typo must not silently make a service more restrictive.

        Becoming *more* restrictive on a typo presents as an authentication
        outage with no obvious cause, so the unparseable case keeps the default
        and complains loudly instead.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "flase")
        with caplog.at_level("ERROR"):
            assert trust_tenant_header() is True
        assert any("not a recognised boolean" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# require_tenant — the negative control
# ---------------------------------------------------------------------------
class TestRequireTenantHeaderGate:
    async def test_forged_header_without_license_is_rejected_when_gate_off(self, monkeypatch):
        """THE security assertion: forged tenant + no license == 401.

        Asserted on the actual outcome. It is not enough that the flag was read;
        the request must not be served, and it must not be quietly handed
        DEFAULT_TENANT_ID either.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        request = _bare_request({"x-tenant-id": VICTIM_TENANT})

        with pytest.raises(HTTPException) as exc_info:
            await require_tenant(request)

        assert exc_info.value.status_code == 401
        assert getattr(request.state, "tenant_id", None) != VICTIM_TENANT

    async def test_forged_header_does_not_downgrade_to_default_tenant(self, monkeypatch):
        """Ignoring the header must not mean 'treat as the default tenant'.

        Silently resolving to DEFAULT_TENANT_ID would swap a cross-tenant read
        for a different cross-tenant read rather than closing anything. This
        held when the fallback was the literal ``"n8n-dev"`` (a real tenant on
        this fleet, which is what made it dangerous) and it still holds now
        that 1.9.0 has removed the literal entirely — the assertion below keeps
        naming it so a re-introduction of the fallback is caught here too.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        request = _bare_request({"x-tenant-id": VICTIM_TENANT})

        with pytest.raises(HTTPException):
            await require_tenant(request)

        assert getattr(request.state, "tenant_id", None) not in (VICTIM_TENANT, "n8n-dev")

    async def test_falls_through_to_license_introspection_when_gate_off(self, monkeypatch):
        """With the gate off the chain continues to Priority 2, and the license wins.

        No header at all, so nothing but fall-through can produce a tenant —
        this proves the chain continues past the disabled header block rather
        than stopping at it.

        ⚠️ This test used to send ``x-tenant-id: VICTIM_TENANT`` alongside the
        license and assert the licensed tenant came back. That shape is now a
        **403** (see ``test_onbehalf_vouching.py``), so it can
        no longer carry the fall-through claim — a 403 and a failure to fall
        through are indistinguishable from the outside. The header was dropped
        rather than the test, because "does the chain continue" is a separate
        question from "may this caller assert that tenant", and both need
        answering.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        request = _bare_request({"Authorization": "Bearer real-license"})

        with _mock_license(LICENSE_TENANT):
            result = await require_tenant(request)

        assert result == LICENSE_TENANT
        assert result != VICTIM_TENANT

    async def test_an_agreeing_header_is_not_an_assertion(self, monkeypatch):
        """The gateway re-injects the tenant it resolved from this same license.

        Every north-south request arrives carrying both headers, so an agreeing
        header must stay a no-op. If this goes red the entire browser-facing
        path 403s the moment coding-gateway is flipped.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        request = _bare_request(
            {"x-tenant-id": LICENSE_TENANT, "Authorization": "Bearer real-license"}
        )

        with _mock_license(LICENSE_TENANT):
            assert await require_tenant(request) == LICENSE_TENANT

    async def test_an_agreeing_header_is_compared_case_insensitively(self, monkeypatch):
        """A casing difference is not a disagreement.

        Same reasoning as above: a false 403 on the north-south path is the
        expensive failure, and widening what counts as "the same tenant" never
        widens *who* may change it.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        request = _bare_request(
            {"x-tenant-id": LICENSE_TENANT.upper(), "Authorization": "Bearer real-license"}
        )

        with _mock_license(LICENSE_TENANT):
            assert await require_tenant(request) == LICENSE_TENANT

    async def test_default_still_honours_the_header(self, monkeypatch):
        """Compatibility guarantee: unset == today's behaviour, exactly.

        This is what makes the merge a no-op live and lets services be flipped
        one at a time. If this goes red, the rollout premise is broken.
        """
        monkeypatch.delenv("TRUST_TENANT_HEADER", raising=False)
        request = _bare_request({"x-tenant-id": VICTIM_TENANT})

        assert await require_tenant(request) == VICTIM_TENANT

    async def test_explicit_true_still_honours_the_header(self, monkeypatch):
        monkeypatch.setenv("TRUST_TENANT_HEADER", "true")
        request = _bare_request({"x-tenant-id": VICTIM_TENANT})
        assert await require_tenant(request) == VICTIM_TENANT

    async def test_gate_off_does_not_disturb_state_populated_tenant(self, monkeypatch):
        """Priority 1 (already-resolved state) is not a header read and is untouched."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        request = _bare_request({})
        request.state.tenant_id = LICENSE_TENANT
        assert await require_tenant(request) == LICENSE_TENANT


# ---------------------------------------------------------------------------
# optional_tenant — the same block, one function down
# ---------------------------------------------------------------------------
class TestOptionalTenantHeaderGate:
    async def test_forged_header_ignored_when_gate_off(self, monkeypatch):
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        request = _bare_request({"x-tenant-id": VICTIM_TENANT})
        result = await optional_tenant(request)
        assert result is None
        assert result != VICTIM_TENANT

    async def test_license_still_resolves_when_gate_off(self, monkeypatch):
        """Fall-through, with no header to confound it — see the require_tenant twin."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        request = _bare_request({"Authorization": "Bearer real-license"})
        with _mock_license(LICENSE_TENANT):
            assert await optional_tenant(request) == LICENSE_TENANT

    async def test_an_agreeing_header_is_not_an_assertion(self, monkeypatch):
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        request = _bare_request(
            {"x-tenant-id": LICENSE_TENANT, "Authorization": "Bearer real-license"}
        )
        with _mock_license(LICENSE_TENANT):
            assert await optional_tenant(request) == LICENSE_TENANT

    async def test_default_still_honours_the_header(self, monkeypatch):
        monkeypatch.delenv("TRUST_TENANT_HEADER", raising=False)
        request = _bare_request({"x-tenant-id": VICTIM_TENANT})
        assert await optional_tenant(request) == VICTIM_TENANT


# ---------------------------------------------------------------------------
# get_current_user_with_tenant — tenant forgery AND role forgery
# ---------------------------------------------------------------------------
class TestGetCurrentUserWithTenantGate:
    def test_forged_admin_role_is_accepted_by_default(self, monkeypatch):
        """Documents the escalation the gate closes.

        `x-user-roles` lands in realm_access, which drives User.is_admin(),
        which require_same_tenant treats as "may read ANY tenant". So the
        default path grants cross-tenant admin to anyone who can set a header.
        This test asserts the current (insecure) behaviour on purpose — it is
        the thing being gated, and it must keep working until a service opts out.
        """
        monkeypatch.delenv("TRUST_TENANT_HEADER", raising=False)
        request = _bare_request({"x-tenant-id": VICTIM_TENANT, "x-user-roles": "admin"})
        user = get_current_user_with_tenant(request)
        assert user.tenant_id == VICTIM_TENANT
        assert user.is_admin() is True

    def test_forged_admin_role_rejected_when_gate_off(self, monkeypatch):
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        request = _bare_request({"x-tenant-id": VICTIM_TENANT, "x-user-roles": "admin"})
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_with_tenant(request)
        assert exc_info.value.status_code == 401

    def test_authmiddleware_supplied_user_still_wins_when_gate_off(self, monkeypatch, mock_user):
        """The gate only removes *header* trust; a real authenticated user is unaffected."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        request = _bare_request({"x-tenant-id": VICTIM_TENANT})
        request.state.user = mock_user
        assert get_current_user_with_tenant(request) is mock_user

    def test_trusted_network_bypass_untouched_when_configured(self, monkeypatch):
        """This PR must not change TRUSTED_CIDRS behaviour — sibling gitops work owns it.

        The tenant is now configured explicitly, which is what the test name
        always claimed. Before 1.9.0 removed the fallback literal this passed
        without configuring anything, because the library invented ``"n8n-dev"``
        — so the assertion was really pinning the invented tenant rather than
        the bypass. Configuring it asserts the actual contract: with the header
        gate OFF, a trusted-network caller still gets the tenant the *operator*
        named. (Same correction 1.9.0 applied to ``TestDevModeApiKey``.)
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        monkeypatch.setattr(tn_mod, "TRUSTED_NETWORKS", [ipaddress.ip_network("10.42.0.0/16")])
        monkeypatch.setattr(dt_mod, "DEFAULT_TENANT_ID", CONFIGURED_TENANT)
        request = _bare_request({}, host="10.42.0.17")
        assert get_current_user_with_tenant(request).tenant_id == CONFIGURED_TENANT

    def test_trusted_network_bypass_rejects_when_no_tenant_configured(self, monkeypatch):
        """False-positive control for the test above.

        Without it, the assertion above would still pass if the bypass branch
        had simply been deleted. With no configured tenant the bypass must
        reject rather than substitute a literal (1.9.0 contract), and the
        header gate must not change that either way.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        monkeypatch.setattr(tn_mod, "TRUSTED_NETWORKS", [ipaddress.ip_network("10.42.0.0/16")])
        monkeypatch.setattr(dt_mod, "DEFAULT_TENANT_ID", None)
        request = _bare_request({}, host="10.42.0.17")
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_with_tenant(request)
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# create_tenant_context
# ---------------------------------------------------------------------------
class TestCreateTenantContextGate:
    def test_forged_header_ignored_when_gate_off(self, monkeypatch):
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        request = _bare_request({"x-tenant-id": VICTIM_TENANT})
        with pytest.raises(HTTPException) as exc_info:
            create_tenant_context(request)
        assert exc_info.value.status_code == 401

    def test_default_still_honours_the_header(self, monkeypatch):
        monkeypatch.delenv("TRUST_TENANT_HEADER", raising=False)
        request = _bare_request({"x-tenant-id": VICTIM_TENANT})
        assert create_tenant_context(request) == {"tenant_id": VICTIM_TENANT}

    def test_license_resolved_state_still_works_when_gate_off(self, monkeypatch):
        """require_tenant runs first on real routes and writes state; that path survives."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        request = _bare_request({"x-tenant-id": VICTIM_TENANT})
        request.state.tenant_id = LICENSE_TENANT
        assert create_tenant_context(request) == {"tenant_id": LICENSE_TENANT}


# ---------------------------------------------------------------------------
# End-to-end through real ASGI middleware — the proof that matters
# ---------------------------------------------------------------------------
def _build_app(*, with_auth_middleware: bool) -> FastAPI:
    app = FastAPI()

    @app.get("/api/whoami")
    async def whoami(tenant_id: str = Depends(require_tenant)):
        return {"tenant_id": tenant_id}

    @app.get("/api/user")
    async def who(request: Request):
        return {"tenant_id": get_current_user_with_tenant(request).tenant_id}

    app.add_middleware(TenantMiddleware)
    if with_auth_middleware:
        app.add_middleware(AuthMiddleware)
    return app


class TestEndToEndThroughMiddleware:
    """Drive a real ASGI stack, because the mocks above cannot prove the
    middleware chain does not re-introduce the header behind the dependency."""

    def test_forged_header_is_served_by_default(self, monkeypatch):
        monkeypatch.delenv("TRUST_TENANT_HEADER", raising=False)
        client = TestClient(_build_app(with_auth_middleware=False))
        resp = client.get("/api/whoami", headers={"X-Tenant-Id": VICTIM_TENANT})
        assert resp.status_code == 200
        assert resp.json() == {"tenant_id": VICTIM_TENANT}

    def test_forged_header_is_rejected_end_to_end_when_gate_off(self, monkeypatch):
        """A forged X-Tenant-Id with no license must not be served the tenant."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        client = TestClient(_build_app(with_auth_middleware=False))
        resp = client.get("/api/whoami", headers={"X-Tenant-Id": VICTIM_TENANT})
        assert resp.status_code == 401
        assert VICTIM_TENANT not in resp.text

    def test_tenant_middleware_does_not_leak_header_into_state_when_gate_off(self, monkeypatch):
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        client = TestClient(_build_app(with_auth_middleware=False))
        resp = client.get("/api/user", headers={"X-Tenant-Id": VICTIM_TENANT})
        assert resp.status_code == 401

    def test_auth_middleware_rejects_header_only_caller_when_gate_off(self, monkeypatch):
        """AuthMiddleware builds a User straight from x-tenant-id/x-user-roles.

        With the gate off it must treat the request as carrying no identity and
        401 it, rather than manufacturing an authenticated user from headers.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        client = TestClient(_build_app(with_auth_middleware=True))
        resp = client.get(
            "/api/whoami",
            headers={"X-Tenant-Id": VICTIM_TENANT, "X-User-Roles": "admin"},
        )
        assert resp.status_code == 401
        assert VICTIM_TENANT not in resp.text

    def test_auth_middleware_accepts_header_caller_by_default(self, monkeypatch):
        monkeypatch.delenv("TRUST_TENANT_HEADER", raising=False)
        client = TestClient(_build_app(with_auth_middleware=True))
        resp = client.get("/api/whoami", headers={"X-Tenant-Id": VICTIM_TENANT})
        assert resp.status_code == 200
        assert resp.json() == {"tenant_id": VICTIM_TENANT}

    def test_public_paths_unaffected(self, monkeypatch):
        """Health endpoints must not start 401ing when a service flips the knob."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        app = _build_app(with_auth_middleware=True)

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        assert TestClient(app).get("/health").status_code == 200
