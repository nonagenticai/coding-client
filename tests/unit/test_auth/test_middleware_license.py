"""AuthMiddleware: authenticating a request from its license token.

What was broken
---------------
Before 1.10.0 ``AuthMiddleware.dispatch`` had **no license introspection at
all**. Its only reference to ``Authorization``/``Bearer`` sat inside a branch
gated on ``ENVIRONMENT in ("development", "testing")``, comparing the token
against a static ``DEV_API_KEY``/``TEST_API_KEY``. ``tenant.py`` documented and
implemented the real thing (``_introspect_license``, 5-minute TTL cache);
``middleware.py`` never called it.

In production that made ``TRUST_TENANT_HEADER=false`` unusable. The dev branch
is skipped, the identity headers are nulled by the gate, and the chain fell
straight through to ``_is_trusted_network`` — which is empty on all nine
``coding-*`` services. Result: **401 for every non-public request, including one
carrying a perfectly valid ``Authorization: Bearer <license>``.**

Live evidence: ``coding-realtime`` already has ``TRUST_TENANT_HEADER=false`` in
``coding-realtime-config`` and was 401ing real traffic from the ``coding-gateway``
pod (``GET /api/stats``, ``GET /api/realtime/connections``) with
``WARNING Unauthenticated request from untrusted network``. The credential was
present at the pod the whole time — the edge Lua filter strips nine identity
headers but never ``authorization``, and coding-gateway's ``_HOP_BY_HOP`` holds
``proxy-authorization`` but not ``authorization``.

What these tests pin down
-------------------------
* A valid Bearer with the gate OFF is served, with the tenant the LICENSE named.
  That is the test that proves the fix.
* Every failure mode of that path is a 401 and never an admit: inactive token,
  no ``tenant_id``, ``LICENSE_INTROSPECT_URL`` unset, introspection raising,
  introspection timing out.
* A forged ``X-Tenant-Id`` with NO Bearer and the gate OFF is **still** 401.
  The security property the gate exists for must not regress — that is the
  whole point of the gate, and this file must not become the thing that
  quietly re-opens it.
* With the gate ON nothing changes: a header caller is served exactly as before
  and introspection is not even consulted.
* A rejected caller is not a 1:1 amplifier into the licenses service. Reading
  the Bearer means an unauthenticated request now costs an outbound POST where
  it used to cost nothing, so failed introspections are cached on a short clock
  — and that cache must expire, and must never replay as an admit. See
  ``TestFailedIntrospectionsAreNegativeCached``.

Test-double discipline
----------------------
Every double for ``_introspect_license`` is built with ``autospec=True``. A
signature-agnostic ``AsyncMock`` is *narrower* than the real coroutine — it
accepts any call at all — so it cannot fail, and it has fabricated passing
results on this fleet before. ``TestTheDoublesThemselves`` below asserts the
autospec really does reject a wrong-arity call, so the discipline is itself
under test rather than merely asserted in a comment.

Where possible the tests do not mock ``_introspect_license`` at all: they patch
``coding_client.auth.tenant.httpx.AsyncClient`` and drive the REAL function.
That is what proves the middleware reuses ``tenant.py``'s implementation and its
cache rather than carrying a second copy of the rule.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from cachetools import TTLCache
from coding_client.auth import _default_tenant as dt_mod
from coding_client.auth import _trusted_networks as tn_mod
from coding_client.auth import tenant as tenant_mod
from coding_client.auth.middleware import AuthMiddleware
from coding_client.auth.tenant import (
    TenantMiddleware,
    clear_license_caches,
    get_current_user_with_tenant,
    require_tenant,
)
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient as FastAPITestClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

LICENSE_TENANT = "licensed-tenant-0001"
VICTIM_TENANT = "victim-tenant-0007"
LICENSE_SUBJECT = "subject-user-42"
CONFIGURED_TENANT = "configured-tenant-0042"
INTROSPECT_URL = "http://test-licenses/license/introspect"


@pytest.fixture(autouse=True)
def _isolate_auth_env(monkeypatch):
    """Neutralise every OTHER way this middleware could mint a user.

    Without this a 200 could come from the dev API key, from SKIP_AUTH, or from
    the trusted-network bypass handing out DEFAULT_TENANT_ID — and the test
    would prove nothing about license introspection.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("SKIP_AUTH", raising=False)
    monkeypatch.delenv("DEV_API_KEY", raising=False)
    monkeypatch.delenv("TEST_API_KEY", raising=False)
    monkeypatch.delenv("TRUST_TENANT_HEADER", raising=False)
    # Vouching off unless a test opts in. Without this, an allowlist inherited
    # from the developer's shell would let an asserted tenant through and the
    # forgery non-regressions below would pass for the wrong reason.
    monkeypatch.delenv("CODING_ONBEHALF_SUBJECTS", raising=False)
    monkeypatch.setenv("LICENSE_INTROSPECT_URL", INTROSPECT_URL)
    monkeypatch.setattr(tn_mod, "TRUSTED_NETWORKS", [])
    monkeypatch.setattr(dt_mod, "DEFAULT_TENANT_ID", None)
    # BOTH caches. A refusal cached by one test would otherwise leak into the
    # next and silently suppress the outbound call it is counting.
    clear_license_caches()
    yield
    clear_license_caches()


def _whoami(request: Request) -> JSONResponse:
    user = getattr(request.state, "user", None)
    if user is None:
        # A 500 here would be indistinguishable from a 401 in a sloppy
        # assertion, so make it loud and distinct.
        return JSONResponse({"error": "no user on request.state"}, status_code=500)
    return JSONResponse(
        {
            "sub": user.sub,
            "username": user.preferred_username,
            "tenant_id": user.tenant_id,
            "effective_tenant_id": user.effective_tenant_id,
            "roles": user.realm_access.get("roles", []),
            "is_admin": user.is_admin(),
        }
    )


def _client() -> TestClient:
    app = Starlette(
        routes=[
            Route("/health", lambda r: JSONResponse({"ok": True})),
            Route("/api/test", _whoami),
        ]
    )
    app.add_middleware(AuthMiddleware)
    return TestClient(app, raise_server_exceptions=False)


def _real_introspection(payload: dict | None, *, status_code: int = 200):
    """Drive the REAL ``_introspect_license`` against a faked HTTP endpoint.

    Patching httpx rather than ``_introspect_license`` is deliberate: it proves
    the middleware goes through ``tenant.py``'s function (and therefore its
    cache), which a mock of the function itself could never show.
    """
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return patch("coding_client.auth.tenant.httpx.AsyncClient", return_value=client), client


def _raising_transport(exc: BaseException):
    """A fake httpx client whose POST raises — timeout / connection failure."""
    client = AsyncMock()
    client.post = AsyncMock(side_effect=exc)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return patch("coding_client.auth.tenant.httpx.AsyncClient", return_value=client)


# ---------------------------------------------------------------------------
# THE fix: a valid license authenticates when header trust is off
# ---------------------------------------------------------------------------
class TestValidLicenseWithGateOff:
    def test_valid_bearer_is_authenticated_when_gate_off(self, monkeypatch):
        """The test that proves the fix.

        Against pre-1.10.0 code this is a 401: the Bearer is never read, and
        with TRUSTED_CIDRS empty there is nothing left to admit on.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, _ = _real_introspection(
            {"active": True, "tenant_id": LICENSE_TENANT, "subject_id": LICENSE_SUBJECT}
        )
        with introspect:
            resp = _client().get("/api/test", headers={"Authorization": "Bearer real-license"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["tenant_id"] == LICENSE_TENANT
        assert body["effective_tenant_id"] == LICENSE_TENANT
        assert body["sub"] == LICENSE_SUBJECT

    def test_the_token_actually_reaches_the_introspection_endpoint(self, monkeypatch):
        """Guard against a pass that comes from anything but the real call."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, fake_http = _real_introspection(
            {"active": True, "tenant_id": LICENSE_TENANT, "subject_id": LICENSE_SUBJECT}
        )
        with introspect:
            resp = _client().get("/api/test", headers={"Authorization": "Bearer tok-abc123"})

        assert resp.status_code == 200
        fake_http.post.assert_awaited_once_with(INTROSPECT_URL, json={"token": "tok-abc123"})

    def test_bearer_scheme_is_case_insensitive(self, monkeypatch):
        """HTTP auth schemes are case-insensitive; `bearer` must work too."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, _ = _real_introspection({"active": True, "tenant_id": LICENSE_TENANT})
        with introspect:
            resp = _client().get("/api/test", headers={"Authorization": "bearer real-license"})
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == LICENSE_TENANT

    def test_license_tenant_beats_a_forged_header_when_gate_off(self, monkeypatch):
        """Fall-through, not merely rejection: the LICENSE names the tenant.

        No asserted header, so the only thing that can name a tenant is the
        license. Serving the licensed one proves the request was admitted for the
        right reason.

        ⚠️ This used to send ``X-Tenant-Id: VICTIM_TENANT`` and assert **200**
        with the licensed tenant. That shape is now **403** — see
        ``test_onbehalf_vouching.py``. Silently downgrading a caller who names a
        tenant it may not name, and serving it its own data instead, hid an
        authorisation failure behind a success. The forged-role half of the claim
        is kept below, where it still applies.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, _ = _real_introspection({"active": True, "tenant_id": LICENSE_TENANT})
        with introspect:
            resp = _client().get(
                "/api/test",
                headers={
                    "Authorization": "Bearer real-license",
                    "X-User-Roles": "admin",
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["tenant_id"] == LICENSE_TENANT
        assert VICTIM_TENANT not in resp.text
        # The forged admin role must not survive either — roles come from the
        # license, and this license names none.
        assert body["roles"] == []
        assert body["is_admin"] is False

    def test_subject_id_is_never_used_as_the_tenant(self, monkeypatch):
        """`subject_id` is the USER; `tenant_id` is the workspace (tenant.py:264)."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, _ = _real_introspection(
            {"active": True, "tenant_id": "the-tenant", "subject_id": "the-user"}
        )
        with introspect:
            resp = _client().get("/api/test", headers={"Authorization": "Bearer tok"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["tenant_id"] == "the-tenant"
        assert body["effective_tenant_id"] == "the-tenant"
        assert body["effective_tenant_id"] != "the-user"

    @pytest.mark.parametrize(
        "payload_subject",
        [{}, {"subject_id": None}, {"subject_id": ""}, {"subject_id": "   "}],
        ids=["absent", "null", "empty", "whitespace"],
    )
    def test_missing_subject_id_uses_the_license_marker_not_an_invented_subject(
        self, monkeypatch, payload_subject
    ):
        """A license with no subject still scopes to its OWN tenant, and its
        ``sub`` is the documented ``license:<tenant>`` MARKER.

        `User.model_post_init` backfills a blank tenant from `sub`, so a
        synthetic subject must never be able to become the tenant.

        This assertion used to be only ``body["sub"] != LICENSE_SUBJECT``, which
        any string satisfies — a substitute such as ``or "anonymous"`` passed
        it. The contract the middleware claims is that the value is obviously
        not a Keycloak subject id (a bare uuid4: never prefixed, never
        containing a colon); assert the exact marker so the comment is not the
        only thing holding it up (nonagenticai/coding-client#60).

        A blank or whitespace-only ``subject_id`` is "no subject named" and takes
        the same marker, for the same reason ``tenant_id`` is stripped: the
        alternative is a ``sub`` of ``"   "``.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, _ = _real_introspection(
            {"active": True, "tenant_id": LICENSE_TENANT, **payload_subject}
        )
        with introspect:
            resp = _client().get("/api/test", headers={"Authorization": "Bearer tok"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["tenant_id"] == LICENSE_TENANT
        assert body["effective_tenant_id"] == LICENSE_TENANT
        # The exact documented marker — kills `or "anonymous"`, a whitespace
        # pass-through, and every other substitute.
        assert body["sub"] == f"license:{LICENSE_TENANT}"
        assert body["username"] == f"license:{LICENSE_TENANT}"
        assert body["sub"] != LICENSE_SUBJECT  # nothing was invented from thin air
        # The tenant is still the LICENSE's, never derived from the marker.
        assert body["effective_tenant_id"] != body["sub"]


# ---------------------------------------------------------------------------
# Roles: from the license or not at all
# ---------------------------------------------------------------------------
class TestRolesComeFromTheLicense:
    """A license says WHICH TENANT you are, never WHAT YOU MAY DO.

    The licenses service returns a Pydantic ``TokenIntrospectResponse``
    (licenses/main.py:497-512) — ``active, tenant_id, license_id, subject_id,
    byo_mode, app, plan, status, starts_at, expires_at, region_id, metadata,
    reason``. There is no ``roles``/``scopes``/``permissions`` field and the
    response_model strips extras, so **a licensed caller is always role-less in
    production**. These tests assert that, rather than the more flattering
    claim that roles flow from the license — which is exactly the claim
    mlx_ingestion_backend and scientific_processor make in their docstrings
    while reading a key that does not exist.
    """

    #: The real production shape, from licenses/main.py:497-512 + models.py:1558.
    PRODUCTION_PAYLOAD = {
        "active": True,
        "tenant_id": LICENSE_TENANT,
        "license_id": "lic-0001",
        "subject_id": LICENSE_SUBJECT,
        "byo_mode": "local_allowed",
        "app": {"id": "app-1", "key": "coding", "name": "Coding", "revoked": False},
        "plan": {"id": "plan-1", "code": "full", "rate_limit_rpm": 600, "quota_monthly": 10000},
        "status": "active",
        "starts_at": "2026-01-01T00:00:00Z",
        "expires_at": "2027-01-01T00:00:00Z",
        "region_id": "eu",
        "metadata": {},
        "reason": None,
    }

    def test_a_real_production_payload_authenticates_with_zero_roles(self, monkeypatch):
        """The whole contract in one test: tenant yes, subject yes, roles no.

        If this ever goes green with a non-empty role list, the licenses service
        started returning authorization data and every consumer's assumptions
        need re-checking.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, _ = _real_introspection(dict(self.PRODUCTION_PAYLOAD))
        with introspect:
            resp = _client().get("/api/test", headers={"Authorization": "Bearer prod-license"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["tenant_id"] == LICENSE_TENANT
        assert body["sub"] == LICENSE_SUBJECT
        assert body["roles"] == []
        assert body["is_admin"] is False

    def test_a_production_payload_never_yields_admin(self, monkeypatch):
        """Negative control on the escalation surface.

        `plan.code == "full"` is a billing tier, not a permission. Nothing in
        the license body may become a role.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        payload = dict(self.PRODUCTION_PAYLOAD)
        payload["plan"] = {"id": "plan-1", "code": "full"}
        payload["metadata"] = {"roles": ["admin"], "is_admin": True}
        introspect, _ = _real_introspection(payload)
        with introspect:
            resp = _client().get("/api/test", headers={"Authorization": "Bearer prod-license"})

        assert resp.status_code == 200
        assert resp.json()["roles"] == []
        assert resp.json()["is_admin"] is False

    def test_roles_absent_means_empty_not_a_default(self, monkeypatch):
        """No role defaults. Empty is the safe end: is_admin() is False, so
        `require_same_tenant` confines the caller to the licensed tenant."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, _ = _real_introspection({"active": True, "tenant_id": LICENSE_TENANT})
        with introspect:
            resp = _client().get("/api/test", headers={"Authorization": "Bearer tok"})

        assert resp.status_code == 200
        assert resp.json()["roles"] == []
        assert resp.json()["is_admin"] is False

    def test_roles_are_honoured_if_the_licenses_service_ever_returns_them(self, monkeypatch):
        """Forward-compatibility only — NOT a claim about today.

        The read is tolerant so that adding `roles` to `TokenIntrospectResponse`
        is a licenses-side change alone. Read together with
        `test_a_real_production_payload_authenticates_with_zero_roles`, which
        pins what actually happens now: no roles, ever.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, _ = _real_introspection(
            {"active": True, "tenant_id": LICENSE_TENANT, "roles": ["admin", "coding-access"]}
        )
        with introspect:
            resp = _client().get("/api/test", headers={"Authorization": "Bearer tok"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["roles"] == ["admin", "coding-access"]
        assert body["is_admin"] is True

    @pytest.mark.parametrize("bad_roles", ["admin", {"roles": ["admin"]}, 7, None])
    def test_non_list_roles_are_ignored_rather_than_coerced(self, monkeypatch, bad_roles):
        """A string would iterate into single characters; a dict into its keys.

        Either would be a silently wrong role set, so anything that is not a
        list of strings yields no roles at all.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, _ = _real_introspection(
            {"active": True, "tenant_id": LICENSE_TENANT, "roles": bad_roles}
        )
        with introspect:
            resp = _client().get("/api/test", headers={"Authorization": "Bearer tok"})

        assert resp.status_code == 200
        assert resp.json()["roles"] == []


# ---------------------------------------------------------------------------
# Fail closed — every failure of the license path is a 401, never an admit
# ---------------------------------------------------------------------------
class TestFailsClosed:
    def test_inactive_license_is_401(self, monkeypatch):
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, _ = _real_introspection({"active": False, "tenant_id": LICENSE_TENANT})
        with introspect:
            resp = _client().get("/api/test", headers={"Authorization": "Bearer expired"})

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Authentication required"
        assert LICENSE_TENANT not in resp.text

    def test_unknown_token_is_401(self, monkeypatch):
        """A 401 from the licenses service itself (no JSON body parsed)."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, _ = _real_introspection(None, status_code=401)
        with introspect:
            resp = _client().get("/api/test", headers={"Authorization": "Bearer bogus"})

        assert resp.status_code == 401

    def test_active_license_without_tenant_id_is_401(self, monkeypatch):
        """Nothing to scope to. Admitting would let `sub` become the tenant."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, _ = _real_introspection({"active": True, "subject_id": LICENSE_SUBJECT})
        with introspect:
            resp = _client().get("/api/test", headers={"Authorization": "Bearer tok"})

        assert resp.status_code == 401
        assert LICENSE_SUBJECT not in resp.text

    @pytest.mark.parametrize(
        "blank",
        ["", "   ", "\t\n", " ", "  \t "],
        ids=["empty", "spaces", "tab-newline", "nbsp", "nbsp-mixed"],
    )
    def test_blank_tenant_id_is_401(self, monkeypatch, blank):
        """Whitespace is blank. `if not tenant_id:` alone was NOT enough.

        ``"   "`` is truthy, so a guard spelled ``if not tenant_id`` waves it
        through — and then ``User.model_post_init`` (models.py:40) does
        ``if not (self.tenant_id or "").strip()`` and backfills the tenant from
        ``sub``. The attacker-controlled ``subject_id`` becomes the tenant: the
        exact outcome the guard exists to prevent, reached through the guard.

        Every form here must be rejected by the SAME rule the rest of the repo
        uses — ``_default_tenant.load_default_tenant_id()`` and ``models.py:40``
        both ``.strip()``. ``str.strip()`` treats U+00A0 NO-BREAK SPACE as
        whitespace, so a tenant that is only a NBSP is blank here too; if it
        were not, it would reach ``model_post_init`` unstripped and stay a
        (bizarre) tenant rather than being backfilled from ``sub``, which is why
        the assertion below is on the SUBJECT never appearing, not merely on the
        status code.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, _ = _real_introspection(
            {"active": True, "tenant_id": blank, "subject_id": LICENSE_SUBJECT}
        )
        with introspect:
            resp = _client().get("/api/test", headers={"Authorization": "Bearer tok"})

        assert resp.status_code == 401
        # The backfill this guard exists to prevent: `sub` must never surface.
        assert LICENSE_SUBJECT not in resp.text

    @pytest.mark.parametrize(
        "bad_tenant",
        [123, True, {"a": 1}, ["tenant"], 1.5, b"tenant"],
        ids=["int", "bool", "dict", "list", "float", "bytes"],
    )
    def test_a_non_string_tenant_id_is_401_not_500(self, monkeypatch, bad_tenant):
        """A malformed introspection body must be a rejection, not a crash.

        ``User.tenant_id`` is ``str | None``, so pydantic raises a
        ``ValidationError`` on any of these. That raise happens while BUILDING
        the user — outside the ``try`` that guards the HTTP call — so it escaped
        ``dispatch`` as a **500**. A 500 is not a rejection anybody audits, and
        it is a free liveness lever for anyone who can influence what the
        introspection endpoint returns.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, _ = _real_introspection(
            {"active": True, "tenant_id": bad_tenant, "subject_id": LICENSE_SUBJECT}
        )
        with introspect:
            resp = _client().get("/api/test", headers={"Authorization": "Bearer tok"})

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Authentication required"
        assert LICENSE_SUBJECT not in resp.text

    @pytest.mark.parametrize(
        "bad_subject",
        [99, True, {"a": 1}, ["subject"], b"subject"],
        ids=["int", "bool", "dict", "list", "bytes"],
    )
    def test_a_non_string_subject_id_is_401_not_500(self, monkeypatch, bad_subject):
        """Same crash, other field. ``sub`` is a required ``str`` on the model.

        Rejecting rather than coercing: a non-string ``subject_id`` means the
        body is not the ``TokenIntrospectResponse`` shape we understand, and
        ``str(99)`` would mint a subject nobody issued.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, _ = _real_introspection(
            {"active": True, "tenant_id": LICENSE_TENANT, "subject_id": bad_subject}
        )
        with introspect:
            resp = _client().get("/api/test", headers={"Authorization": "Bearer tok"})

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Authentication required"
        assert LICENSE_TENANT not in resp.text

    @pytest.mark.parametrize(
        "body",
        ["not-a-dict", 42, ["active"], True],
        ids=["str", "int", "list", "bool"],
    )
    def test_a_non_dict_introspection_body_is_401_not_500(self, monkeypatch, body):
        """``license_data.get(...)`` on a non-dict is an ``AttributeError``."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, _ = _real_introspection(body)
        with introspect:
            resp = _client().get("/api/test", headers={"Authorization": "Bearer tok"})

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Authentication required"

    def test_a_user_construction_failure_is_401_not_500(self, monkeypatch):
        """The structural assertion behind the two tests above.

        They would also pass if the type checks happened to catch every shape
        pydantic rejects — a coincidence that decays the moment ``User`` grows a
        field. This one proves the ``User(...)`` build itself sits INSIDE the
        guarded region, so *any* future raise there is a 401 rather than a 500.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, _ = _real_introspection({"active": True, "tenant_id": LICENSE_TENANT})
        with introspect:
            with patch(
                "coding_client.auth.middleware.User",
                side_effect=RuntimeError("model build blew up"),
            ):
                resp = _client().get("/api/test", headers={"Authorization": "Bearer tok"})

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Authentication required"

    def test_introspect_url_unset_is_401_and_does_not_raise(self, monkeypatch):
        """An unset URL means "this path yields no identity" — tenant.py:81-83.

        `_introspect_license` returns None rather than raising. That must stay
        a 401 (not a 500, not an admit): a misconfigured Deployment is an outage
        for licensed callers, never a hole for unlicensed ones.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        monkeypatch.delenv("LICENSE_INTROSPECT_URL", raising=False)
        monkeypatch.setattr("coding_client.auth.tenant.LICENSE_INTROSPECT_URL", "")

        # No httpx patch at all: if the code tried to make a real call this
        # would not be a clean 401.
        resp = _client().get("/api/test", headers={"Authorization": "Bearer real-license"})

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Authentication required"

    def test_introspection_timeout_is_401(self, monkeypatch):
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        with _raising_transport(httpx.TimeoutException("timed out")):
            resp = _client().get("/api/test", headers={"Authorization": "Bearer tok"})

        assert resp.status_code == 401

    def test_introspection_connect_error_is_401(self, monkeypatch):
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        with _raising_transport(httpx.ConnectError("licenses service down")):
            resp = _client().get("/api/test", headers={"Authorization": "Bearer tok"})

        assert resp.status_code == 401

    def test_introspection_raising_outright_is_401_not_500(self, monkeypatch):
        """Belt to the braces: if `_introspect_license` itself ever raised, an
        escaping exception would be a 500, and a 500 is not a rejection."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        with patch(
            "coding_client.auth.middleware._introspect_license",
            autospec=True,
            side_effect=RuntimeError("boom"),
        ):
            resp = _client().get("/api/test", headers={"Authorization": "Bearer tok"})

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Authentication required"

    def test_introspection_returning_none_is_401(self, monkeypatch):
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        with patch(
            "coding_client.auth.middleware._introspect_license",
            autospec=True,
            return_value=None,
        ):
            resp = _client().get("/api/test", headers={"Authorization": "Bearer tok"})

        assert resp.status_code == 401

    @pytest.mark.parametrize(
        "header",
        [
            "Basic dXNlcjpwYXNz",  # pragma: allowlist secret
            "Bearer",
            "Bearer ",
            "Bearer    ",
            "Token abc",
            "",
        ],
    )
    def test_non_bearer_or_empty_credentials_never_introspect(self, monkeypatch, header):
        """No token means no call and no user — not an empty-string lookup."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        with patch(
            "coding_client.auth.middleware._introspect_license", autospec=True
        ) as introspect:
            resp = _client().get("/api/test", headers={"Authorization": header})

        assert resp.status_code == 401
        introspect.assert_not_awaited()


class TestDevKeyBranchDoesNotShortCircuitTheChain:
    """The dev/test API-key block sits ABOVE everything else in ``dispatch``.

    It reads the same ``Authorization`` header the license path reads, so its
    skip-path is on the way to every verified identity. Covering it also takes
    the FALSE edge of ``if auth_header.lower().startswith("bearer ")`` inside
    ``if is_dev_or_test:``, which no test in this module exercised.
    """

    @pytest.mark.parametrize("environment", ["development", "testing"])
    def test_a_configured_dev_key_admits_nobody_who_does_not_present_it(
        self, monkeypatch, environment
    ):
        """No Authorization header at all, in a dev/test environment, with both
        API keys AND a default tenant configured. Still 401."""
        monkeypatch.setenv("ENVIRONMENT", environment)
        monkeypatch.setenv("DEV_API_KEY", "dev-key-abc")  # pragma: allowlist secret
        monkeypatch.setenv("TEST_API_KEY", "test-key-abc")  # pragma: allowlist secret
        monkeypatch.setattr(dt_mod, "DEFAULT_TENANT_ID", CONFIGURED_TENANT)
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")

        resp = _client().get("/api/test")

        assert resp.status_code == 401
        assert CONFIGURED_TENANT not in resp.text

    def test_a_non_bearer_scheme_in_dev_mode_does_not_reach_the_key_comparison(self, monkeypatch):
        """A Basic credential must not be compared against the dev key."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("DEV_API_KEY", "dev-key-abc")  # pragma: allowlist secret
        monkeypatch.setattr(dt_mod, "DEFAULT_TENANT_ID", CONFIGURED_TENANT)
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")

        resp = _client().get("/api/test", headers={"Authorization": "Basic ZGV2LWtleS1hYmM="})

        assert resp.status_code == 401
        assert CONFIGURED_TENANT not in resp.text

    def test_a_real_license_still_wins_in_dev_mode_when_the_key_does_not_match(self, monkeypatch):
        """The dev block does not consume the Bearer it fails to recognise."""
        monkeypatch.setenv("ENVIRONMENT", "testing")
        monkeypatch.setenv("TEST_API_KEY", "some-other-key")  # pragma: allowlist secret
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, _ = _real_introspection({"active": True, "tenant_id": LICENSE_TENANT})
        with introspect:
            resp = _client().get("/api/test", headers={"Authorization": "Bearer real-license"})

        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == LICENSE_TENANT


# ---------------------------------------------------------------------------
# The security property the gate exists for — must NOT regress
# ---------------------------------------------------------------------------
class TestHeaderForgeryStillRejectedWithGateOff:
    def test_forged_tenant_header_with_no_bearer_is_still_401(self, monkeypatch):
        """THE non-regression assertion.

        Adding a license path must not become a way back in for a header-only
        caller. No credential, gate off => 401, and the claimed tenant must not
        appear anywhere in the response.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        resp = _client().get("/api/test", headers={"X-Tenant-Id": VICTIM_TENANT})

        assert resp.status_code == 401
        assert VICTIM_TENANT not in resp.text

    def test_forged_admin_role_with_no_bearer_is_still_401(self, monkeypatch):
        """`x-user-roles` feeds User.is_admin(), which require_same_tenant reads
        as "may access ANY tenant". Role forgery must stay closed too."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        resp = _client().get(
            "/api/test",
            headers={
                "X-Tenant-Id": VICTIM_TENANT,
                "X-User-Id": "attacker",
                "X-User-Roles": "admin,platform-admin",
            },
        )

        assert resp.status_code == 401
        assert VICTIM_TENANT not in resp.text

    def test_forged_header_is_not_downgraded_to_the_default_tenant(self, monkeypatch):
        """Rejecting must not mean "serve DEFAULT_TENANT_ID instead" — that
        swaps one cross-tenant read for another rather than closing anything."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        monkeypatch.setattr(dt_mod, "DEFAULT_TENANT_ID", CONFIGURED_TENANT)
        resp = _client().get("/api/test", headers={"X-Tenant-Id": VICTIM_TENANT})

        assert resp.status_code == 401
        assert VICTIM_TENANT not in resp.text
        assert CONFIGURED_TENANT not in resp.text
        assert "n8n-dev" not in resp.text

    def test_forged_header_plus_invalid_bearer_is_401(self, monkeypatch):
        """The two failing paths must not add up to a passing one."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, _ = _real_introspection({"active": False})
        with introspect:
            resp = _client().get(
                "/api/test",
                headers={"X-Tenant-Id": VICTIM_TENANT, "Authorization": "Bearer expired"},
            )

        assert resp.status_code == 401
        assert VICTIM_TENANT not in resp.text


# ---------------------------------------------------------------------------
# Gate ON — the compatibility guarantee the per-service rollout depends on
# ---------------------------------------------------------------------------
class TestGateOnIsUnchanged:
    @pytest.mark.parametrize("gate", [None, "true", "1", "yes", "on"])
    def test_header_caller_is_served_and_introspection_is_not_consulted(self, monkeypatch, gate):
        """With header trust on, this change is invisible: the header still
        wins and the license endpoint is never called."""
        if gate is None:
            monkeypatch.delenv("TRUST_TENANT_HEADER", raising=False)
        else:
            monkeypatch.setenv("TRUST_TENANT_HEADER", gate)

        with patch(
            "coding_client.auth.middleware._introspect_license", autospec=True
        ) as introspect:
            resp = _client().get(
                "/api/test",
                headers={
                    "X-User-Id": "istio-user-42",
                    "X-Tenant-Id": "tenant-99",
                    "X-User-Roles": "admin,user",
                    "Authorization": "Bearer some-license",
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["sub"] == "istio-user-42"
        assert body["tenant_id"] == "tenant-99"
        assert body["roles"] == ["admin", "user"]
        introspect.assert_not_awaited()

    def test_valid_bearer_also_works_with_the_gate_on(self, monkeypatch):
        """Additive, not conditional: the new path is not keyed to the gate.

        A service that has not flipped the knob but sends no identity headers
        (nothing on this fleet forbids that) now authenticates by license
        instead of 401ing.
        """
        monkeypatch.delenv("TRUST_TENANT_HEADER", raising=False)
        introspect, _ = _real_introspection({"active": True, "tenant_id": LICENSE_TENANT})
        with introspect:
            resp = _client().get("/api/test", headers={"Authorization": "Bearer real-license"})

        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == LICENSE_TENANT

    def test_public_paths_never_introspect(self, monkeypatch):
        """Health endpoints must not start calling the licenses service."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        with patch(
            "coding_client.auth.middleware._introspect_license", autospec=True
        ) as introspect:
            resp = _client().get("/health", headers={"Authorization": "Bearer tok"})

        assert resp.status_code == 200
        introspect.assert_not_awaited()

    def test_trusted_network_bypass_still_works_when_armed(self, monkeypatch):
        """The new block sits ABOVE the bypass; it must not have shadowed it."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        monkeypatch.setattr(dt_mod, "DEFAULT_TENANT_ID", CONFIGURED_TENANT)
        with patch("coding_client.auth.middleware._is_trusted_network", return_value=True):
            resp = _client().get("/api/test")

        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == CONFIGURED_TENANT
        assert resp.json()["username"] == "internal"

    def test_a_real_license_beats_the_trusted_network_guess(self, monkeypatch):
        """Verified identity outranks "your IP looks local"."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        monkeypatch.setattr(dt_mod, "DEFAULT_TENANT_ID", CONFIGURED_TENANT)
        introspect, _ = _real_introspection({"active": True, "tenant_id": LICENSE_TENANT})
        with introspect:
            with patch("coding_client.auth.middleware._is_trusted_network", return_value=True):
                resp = _client().get("/api/test", headers={"Authorization": "Bearer real-license"})

        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == LICENSE_TENANT
        assert CONFIGURED_TENANT not in resp.text


# ---------------------------------------------------------------------------
# One implementation, one cache
# ---------------------------------------------------------------------------
class TestSharesTenantModuleImplementation:
    def test_middleware_calls_tenant_modules_function(self):
        """Not a second copy of the rule. Two implementations of one rule is how
        TRUSTED_CIDRS and DEFAULT_TENANT_ID ended up permissive in one file and
        fixed in the other."""
        from coding_client.auth import middleware as mw
        from coding_client.auth import tenant as tn

        assert mw._introspect_license is tn._introspect_license

    def test_second_request_is_served_from_the_shared_cache(self, monkeypatch):
        """The 5-minute TTL cache in tenant.py covers the middleware path too:
        two requests with the same token make ONE HTTP call."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, fake_http = _real_introspection({"active": True, "tenant_id": LICENSE_TENANT})
        with introspect:
            client = _client()
            first = client.get("/api/test", headers={"Authorization": "Bearer same-token"})
            second = client.get("/api/test", headers={"Authorization": "Bearer same-token"})

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["tenant_id"] == LICENSE_TENANT
        assert fake_http.post.await_count == 1


class TestFailedIntrospectionsAreNegativeCached:
    """A rejected caller must not be a 1:1 amplifier into the licenses service.

    What this class replaces
    ------------------------
    The original ``test_an_inactive_license_is_not_cached`` asserted
    ``await_count == 2`` and called that the contract. It was accurate about the
    code and it DOCUMENTED an amplification: ``tenant.py`` cached only when
    ``data.get("active")``, so every failed introspection was a fresh POST — and
    a fresh ``httpx.AsyncClient``, therefore a fresh TCP connection — to
    ``licenses.licenses.svc.cluster.local:8544``, which ``licenses/main.py:820``
    calls "the fleet's hottest auth path". Before ``_user_from_license`` existed
    a garbage Bearer cost zero outbound calls, because nothing read the header.
    Adding the license path turned any unauthenticated caller that can reach a
    gate-off ``coding-*`` port into a 1:1 fan-out amplifier against shared infra.

    The contract now: a failed or inactive introspection is cached too, on a much
    shorter clock than the 5-minute positive TTL. Short so a revoked license is
    not honoured — sorry, *rejected* — for long after it is re-issued; non-zero
    so a hot loop cannot fan out one-for-one.

    ⚠️ Scope, stated so it is not mistaken for more than it is: this dampens
    REPEATED presentations of the SAME token. An attacker rotating tokens gets a
    fresh cache key every time and still fans out 1:1 — the cache is bounded
    (LRU) precisely because those keys are attacker-controlled. Rate limiting at
    the edge is the answer to that; this is not.
    """

    def test_an_inactive_license_is_not_re_introspected_on_every_request(self, monkeypatch):
        """The rewritten original. Was: ``assert await_count == 2``."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, fake_http = _real_introspection({"active": False})
        with introspect:
            client = _client()
            first = client.get("/api/test", headers={"Authorization": "Bearer revoked"})
            second = client.get("/api/test", headers={"Authorization": "Bearer revoked"})

        # Still rejected — dampening must never turn into admitting.
        assert first.status_code == 401
        assert second.status_code == 401
        assert fake_http.post.await_count == 1

    def test_an_unknown_token_is_not_re_introspected_on_every_request(self, monkeypatch):
        """A non-200 from the licenses service is a decision too."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, fake_http = _real_introspection(None, status_code=401)
        with introspect:
            client = _client()
            for _ in range(5):
                assert (
                    client.get("/api/test", headers={"Authorization": "Bearer bogus"}).status_code
                    == 401
                )

        assert fake_http.post.await_count == 1

    def test_an_unreachable_licenses_service_is_not_hammered(self, monkeypatch):
        """The case that matters most: the service is already down.

        A retry storm against a recovering dependency is how a blip becomes an
        outage. The cost is bounded and small — a token presented while the
        service was down waits out the short negative TTL after it recovers.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        client_double = AsyncMock()
        client_double.post = AsyncMock(side_effect=httpx.ConnectError("licenses service down"))
        client_double.__aenter__ = AsyncMock(return_value=client_double)
        client_double.__aexit__ = AsyncMock(return_value=False)
        with patch("coding_client.auth.tenant.httpx.AsyncClient", return_value=client_double):
            client = _client()
            for _ in range(5):
                assert (
                    client.get("/api/test", headers={"Authorization": "Bearer tok"}).status_code
                    == 401
                )

        assert client_double.post.await_count == 1

    def test_the_negative_entry_expires_so_a_reissued_license_is_not_locked_out(self, monkeypatch):
        """Bounded in TIME, not just in size.

        A negative cache that outlived its usefulness would be a denial of
        service against the caller whose license was just renewed. The clock is
        faked rather than slept on, so this is deterministic; the REAL ttl value
        is pinned separately by
        ``test_the_negative_ttl_is_far_shorter_than_the_positive_ttl``.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")

        now = [1000.0]
        fake_negative_cache = TTLCache(maxsize=64, ttl=10, timer=lambda: now[0])
        monkeypatch.setattr(
            tenant_mod, "_negative_license_cache", fake_negative_cache, raising=False
        )

        introspect, fake_http = _real_introspection({"active": False})
        with introspect:
            client = _client()
            client.get("/api/test", headers={"Authorization": "Bearer renewed"})
            client.get("/api/test", headers={"Authorization": "Bearer renewed"})
            assert fake_http.post.await_count == 1, "the second call should have been dampened"

            now[0] += 11  # past the negative ttl
            client.get("/api/test", headers={"Authorization": "Bearer renewed"})

        assert fake_http.post.await_count == 2

    def test_the_negative_ttl_is_far_shorter_than_the_positive_ttl(self):
        """The knob, pinned. An EXACT value, not a floor.

        A range assertion would survive someone "harmonising" the two TTLs at
        300s, which is the change this test exists to stop: a revoked license
        must not stay rejected for five minutes after it is re-issued, and an
        outage blip must not become a five-minute one.
        """
        assert tenant_mod.NEGATIVE_CACHE_TTL_SECONDS == 10
        assert tenant_mod.POSITIVE_CACHE_TTL_SECONDS == 300
        assert tenant_mod._negative_license_cache.ttl == 10
        assert tenant_mod._license_cache.ttl == 300
        # Bounded, and bounded by a caller-controlled key space: any garbage
        # token mints an entry, so this MUST have a maxsize.
        assert tenant_mod._negative_license_cache.maxsize == 1000

    def test_a_valid_license_is_still_served_from_the_positive_cache(self, monkeypatch):
        """Negative caching must not have displaced the positive one."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, fake_http = _real_introspection({"active": True, "tenant_id": LICENSE_TENANT})
        with introspect:
            client = _client()
            first = client.get("/api/test", headers={"Authorization": "Bearer good"})
            second = client.get("/api/test", headers={"Authorization": "Bearer good"})

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["tenant_id"] == LICENSE_TENANT
        assert fake_http.post.await_count == 1

    def test_a_negative_decision_never_becomes_an_admit(self, monkeypatch):
        """The cache stores the DECISION, not a bare "we asked".

        A cached ``None`` read back as "no answer yet, fall through" would be
        the amplification fix turning into an authentication bypass.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        monkeypatch.setattr(dt_mod, "DEFAULT_TENANT_ID", CONFIGURED_TENANT)
        introspect, _ = _real_introspection({"active": False, "tenant_id": VICTIM_TENANT})
        with introspect:
            client = _client()
            for _ in range(3):
                resp = client.get("/api/test", headers={"Authorization": "Bearer revoked"})
                assert resp.status_code == 401
                assert VICTIM_TENANT not in resp.text
                assert CONFIGURED_TENANT not in resp.text


# ---------------------------------------------------------------------------
# The doubles themselves — a mock narrower than the real thing cannot fail
# ---------------------------------------------------------------------------
class TestTheDoublesThemselves:
    """`autospec=True` is asserted, not assumed.

    A bare `AsyncMock()` accepts *any* call — wrong arity, wrong keywords — so a
    test built on one passes even when the code under test calls something that
    does not exist. This class proves the autospec doubles used above really do
    reject a call the real coroutine would reject.
    """

    async def test_autospec_double_rejects_a_wrong_arity_call(self):
        with patch(
            "coding_client.auth.middleware._introspect_license", autospec=True
        ) as introspect:
            with pytest.raises(TypeError):
                await introspect("token", "an-extra-positional-arg")

    async def test_autospec_double_rejects_an_unknown_keyword(self):
        with patch(
            "coding_client.auth.middleware._introspect_license", autospec=True
        ) as introspect:
            with pytest.raises(TypeError):
                await introspect(token="tok", tenant_id="not-a-parameter")

    async def test_a_bare_asyncmock_would_have_accepted_both(self):
        """The negative control that makes the two tests above meaningful."""
        loose = AsyncMock()
        await loose("token", "an-extra-positional-arg")
        await loose(token="tok", tenant_id="not-a-parameter")


# ---------------------------------------------------------------------------
# The fleet-level claim: 8 of 9 services unblocked with ZERO caller changes
# ---------------------------------------------------------------------------
def _full_stack_app() -> FastAPI:
    """The real shape a coding-* service runs: AuthMiddleware + TenantMiddleware
    in front of the two dependencies services actually resolve identity with."""
    app = FastAPI()

    @app.get("/api/whoami")
    async def whoami(tenant_id: str = Depends(require_tenant)):
        return {"tenant_id": tenant_id}

    @app.get("/api/user")
    async def who(request: Request):
        user = get_current_user_with_tenant(request)
        return {"tenant_id": user.tenant_id, "sub": user.sub, "is_admin": user.is_admin()}

    app.add_middleware(TenantMiddleware)
    app.add_middleware(AuthMiddleware)
    return app


class TestUnblocksTheDownstreamDependencies:
    """Middleware minting a User is only half the fix.

    A service is unblocked only if the dependency it resolves identity with
    also stops 401ing. These drive the whole stack, because a unit test of
    ``dispatch`` cannot show that ``require_tenant`` Priority 3 and
    ``get_current_user_with_tenant`` Priority 1 pick the license user up.
    """

    def test_require_tenant_resolves_from_the_license_user_when_gate_off(self, monkeypatch):
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, _ = _real_introspection({"active": True, "tenant_id": LICENSE_TENANT})
        with introspect:
            resp = FastAPITestClient(_full_stack_app()).get(
                "/api/whoami", headers={"Authorization": "Bearer real-license"}
            )

        assert resp.status_code == 200
        assert resp.json() == {"tenant_id": LICENSE_TENANT}

    def test_get_current_user_with_tenant_resolves_when_gate_off(self, monkeypatch):
        """This dependency is SYNC and therefore cannot introspect on its own
        (tenant.py:377-381). Before 1.10.0 that made it unusable with the gate
        off. It works now because its Priority 1 reads ``request.state.user``,
        which AuthMiddleware finally populates from the license.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, _ = _real_introspection(
            {"active": True, "tenant_id": LICENSE_TENANT, "subject_id": LICENSE_SUBJECT}
        )
        with introspect:
            resp = FastAPITestClient(_full_stack_app()).get(
                "/api/user", headers={"Authorization": "Bearer real-license"}
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["tenant_id"] == LICENSE_TENANT
        assert body["sub"] == LICENSE_SUBJECT
        assert body["is_admin"] is False

    def test_tenant_middleware_does_not_overwrite_the_license_tenant(self, monkeypatch):
        """TenantMiddleware runs after AuthMiddleware and rewrites
        ``user.tenant_id`` from the header when it trusts headers. With the gate
        off it must leave the license-resolved tenant alone.

        The header here **agrees** with the license, which is the shape the real
        stack sees: coding-gateway re-injects the tenant it resolved from this
        same token. That still exercises the claim — TenantMiddleware's header
        read is live and would rewrite ``user.tenant_id`` from it — while no
        longer depending on a disagreeing header, which is now a 403.
        """
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        introspect, _ = _real_introspection({"active": True, "tenant_id": LICENSE_TENANT})
        with introspect:
            resp = FastAPITestClient(_full_stack_app()).get(
                "/api/user",
                headers={"Authorization": "Bearer real-license", "X-Tenant-Id": LICENSE_TENANT},
            )

        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == LICENSE_TENANT
        assert VICTIM_TENANT not in resp.text

    @pytest.mark.parametrize("route", ["/api/whoami", "/api/user"])
    def test_both_dependencies_still_reject_a_forged_header_when_gate_off(self, monkeypatch, route):
        """The non-regression, end to end through the real stack."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        resp = FastAPITestClient(_full_stack_app()).get(
            route, headers={"X-Tenant-Id": VICTIM_TENANT, "X-User-Roles": "admin"}
        )

        assert resp.status_code == 401
        assert VICTIM_TENANT not in resp.text

    @pytest.mark.parametrize("route", ["/api/whoami", "/api/user"])
    def test_both_dependencies_unchanged_with_the_gate_on(self, monkeypatch, route):
        monkeypatch.delenv("TRUST_TENANT_HEADER", raising=False)
        resp = FastAPITestClient(_full_stack_app()).get(
            route, headers={"X-Tenant-Id": "tenant-99", "X-User-Id": "u1"}
        )

        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == "tenant-99"

    def test_a_service_with_no_introspect_url_configured_gets_401_not_500(self, monkeypatch):
        """coding-jobs / coding-llm-bootstrap / coding-repo-jobs set no
        LICENSE_INTROSPECT_URL. Flipping the gate on those is an outage for
        licensed callers, logged at ERROR — never a crash, never an admit."""
        monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
        monkeypatch.delenv("LICENSE_INTROSPECT_URL", raising=False)
        monkeypatch.setattr("coding_client.auth.tenant.LICENSE_INTROSPECT_URL", "")

        resp = FastAPITestClient(_full_stack_app(), raise_server_exceptions=False).get(
            "/api/whoami", headers={"Authorization": "Bearer real-license"}
        )

        assert resp.status_code == 401
