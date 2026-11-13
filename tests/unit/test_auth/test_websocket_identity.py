"""WebSocket identity resolution — the one path no middleware can protect.

`AuthMiddleware` is a `BaseHTTPMiddleware`; Starlette never invokes `dispatch`
on a `websocket` scope. So once the HTTP paths stopped trusting a bare
X-Tenant-Id, WS handlers became the only place a pod could still assert any
tenant and be believed. These pin the replacement rule.

As of 1.15.0 the uncredentialed residual is closed: `should_close` is True for
NO_CREDENTIAL as well as REFUSED. `TestTheDecisionToClose` below is the class
that holds that shut — every one of its cases fails if `should_close` is reverted
to `outcome is Outcome.REFUSED`.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from coding_client.auth import _default_tenant as dt_mod
from coding_client.auth import _onbehalf as ob_mod
from coding_client.auth import _trusted_networks as tn_mod
from coding_client.auth.tenant import clear_license_caches
from coding_client.auth.websocket import (
    Outcome,
    WebSocketIdentity,
    resolve_websocket_identity,
)

SERVICE_SUBJECT = "019ffa19-db80-700e-9840-8c17e23b35d5"
OTHER_SUBJECT = "019ff971-7cbf-7505-8bad-1f86ab493f6e"
SERVICE_TENANT = "service-own-tenant-0001"
CUSTOMER_TENANT = "customer-tenant-0042"
INTROSPECT_URL = "http://test-licenses/license/introspect"


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("SKIP_AUTH", raising=False)
    monkeypatch.delenv("CODING_ONBEHALF_SUBJECTS", raising=False)
    monkeypatch.setenv("TRUST_TENANT_HEADER", "false")
    monkeypatch.setenv("LICENSE_INTROSPECT_URL", INTROSPECT_URL)
    monkeypatch.setattr(tn_mod, "TRUSTED_NETWORKS", [])
    monkeypatch.setattr(dt_mod, "DEFAULT_TENANT_ID", None)
    ob_mod._warned_synthetic.clear()
    clear_license_caches()
    yield
    clear_license_caches()


def _introspection(payload: dict | None):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = payload
    client = AsyncMock()
    client.post = AsyncMock(return_value=resp)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return patch("coding_client.auth.tenant.httpx.AsyncClient", return_value=client)


def _ws(headers: dict[str, str]):
    """A stand-in exposing exactly what the resolver reads off a WebSocket.

    Starlette's WebSocket and Request both expose `.headers` and `.url`, which is
    the whole reason the HTTP and WS paths can share one decision function.
    """
    ws = MagicMock()
    ws.headers = {k.lower(): v for k, v in headers.items()}
    ws.url.path = "/api/quality/ws/c1"
    return ws


def _licence(subject: str = SERVICE_SUBJECT) -> dict:
    return {"active": True, "tenant_id": SERVICE_TENANT, "subject_id": subject}


class TestWebSocketIdentity:
    async def test_an_allowlisted_proxy_may_act_for_the_customer(self, monkeypatch):
        """The shape that keeps a browser-originated socket working.

        A browser cannot set Authorization on a handshake, so the PROXY presents
        its own licence and names the customer in X-Tenant-Id.
        """
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", SERVICE_SUBJECT)
        with _introspection(_licence()):
            ident = await resolve_websocket_identity(
                _ws({"authorization": "Bearer gw", "x-tenant-id": CUSTOMER_TENANT})
            )
        assert ident.outcome is Outcome.RESOLVED
        assert ident.tenant_id == CUSTOMER_TENANT
        assert ident.should_close is False

    async def test_a_non_allowlisted_credential_is_refused(self, monkeypatch):
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", OTHER_SUBJECT)
        with _introspection(_licence()):
            ident = await resolve_websocket_identity(
                _ws({"authorization": "Bearer gw", "x-tenant-id": CUSTOMER_TENANT})
            )
        assert ident.outcome is Outcome.REFUSED
        assert ident.should_close is True
        assert ident.tenant_id is None

    async def test_a_refusal_never_echoes_the_asserted_tenant(self, monkeypatch):
        """Echoing it back confirms the guess to whoever sent it."""
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", OTHER_SUBJECT)
        with _introspection(_licence()):
            ident = await resolve_websocket_identity(
                _ws({"authorization": "Bearer gw", "x-tenant-id": CUSTOMER_TENANT})
            )
        assert CUSTOMER_TENANT not in (ident.reason or "")

    async def test_an_empty_allowlist_refuses(self):
        with _introspection(_licence()):
            ident = await resolve_websocket_identity(
                _ws({"authorization": "Bearer gw", "x-tenant-id": CUSTOMER_TENANT})
            )
        assert ident.outcome is Outcome.REFUSED

    async def test_an_agreeing_header_is_not_an_assertion(self):
        with _introspection(_licence()):
            ident = await resolve_websocket_identity(
                _ws({"authorization": "Bearer gw", "x-tenant-id": SERVICE_TENANT})
            )
        assert ident.outcome is Outcome.RESOLVED
        assert ident.tenant_id == SERVICE_TENANT

    async def test_no_assertion_resolves_to_the_licence_tenant(self):
        with _introspection(_licence()):
            ident = await resolve_websocket_identity(_ws({"authorization": "Bearer gw"}))
        assert ident.outcome is Outcome.RESOLVED
        assert ident.tenant_id == SERVICE_TENANT

    async def test_a_bare_forged_header_yields_no_credential_not_a_tenant(self):
        """The forgery this exists to stop: a header alone proves nothing.

        It is reported as NO_CREDENTIAL rather than RESOLVED — the handler must
        never receive a tenant it can act on from an unauthenticated handshake.
        """
        ident = await resolve_websocket_identity(_ws({"x-tenant-id": CUSTOMER_TENANT}))
        assert ident.outcome is Outcome.NO_CREDENTIAL
        assert ident.tenant_id is None

    async def test_no_credential_is_not_reported_as_refused(self):
        """The enum stays three-valued even though the decision is now shared.

        1.15.0 made `should_close` True for NO_CREDENTIAL, but it did NOT
        collapse the outcome into REFUSED. "A credential, but not for that
        tenant" and "no credential at all" are different operational facts and
        want different log lines; a consumer that reports them identically
        cannot tell an unconverted caller from an attempted forgery.
        """
        ident = await resolve_websocket_identity(_ws({}))
        assert ident.outcome is Outcome.NO_CREDENTIAL
        assert ident.outcome is not Outcome.REFUSED
        assert ident.tenant_id is None

    async def test_an_inactive_licence_is_not_a_credential(self):
        with _introspection({"active": False, "reason": "token_invalid"}):
            ident = await resolve_websocket_identity(
                _ws({"authorization": "Bearer revoked", "x-tenant-id": CUSTOMER_TENANT})
            )
        assert ident.outcome is Outcome.NO_CREDENTIAL
        assert ident.tenant_id is None
        # A revoked token proves nothing, so it buys nothing: closed since 1.15.0.
        assert ident.should_close is True

    async def test_the_forwarded_customer_licence_is_captured(self, monkeypatch):
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", SERVICE_SUBJECT)
        lic = "019ff6c4-bff2-76a8-8fb4-fefd2ca9bdc1"
        with _introspection(_licence()):
            ident = await resolve_websocket_identity(
                _ws(
                    {
                        "authorization": "Bearer gw",
                        "x-tenant-id": CUSTOMER_TENANT,
                        "x-license-id": lic,
                    }
                )
            )
        assert ident.license_id == lic

    async def test_the_identity_is_frozen(self, monkeypatch):
        """A handler must not be able to widen a decision after it was made."""
        import dataclasses

        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", OTHER_SUBJECT)
        with _introspection(_licence()):
            ident = await resolve_websocket_identity(
                _ws({"authorization": "Bearer gw", "x-tenant-id": CUSTOMER_TENANT})
            )
        with pytest.raises(dataclasses.FrozenInstanceError):
            ident.tenant_id = CUSTOMER_TENANT  # type: ignore[misc]


class TestTheDecisionToClose:
    """`should_close` is the whole contract a handler is allowed to act on.

    Until 1.15.0 it was True only for REFUSED, so an uncredentialed handshake —
    a raw forged `X-Tenant-Id` and nothing else — fell through and both
    consumers served another tenant's live stream (reproduced from inside the
    pods on coding-realtime `/api/broadcast/subscribe`, coding-realtime
    `/api/realtime/analysis` and coding-analysis `/api/quality/ws/{container}`).

    That was an instrument, not a safety property: the WARNING it emitted was
    there to find the callers still to convert. Over full log retention it fired
    5 times on coding-realtime — all `peer=127.0.0.1`, a verification probe —
    and 0 times on coding-analysis, while both real callers (coding-gateway and
    fr) became credentialed. The reading is in; the residual is closed.

    Every test in this class fails against
    `return self.outcome is Outcome.REFUSED`.
    """

    async def test_an_uncredentialed_handshake_must_now_close(self):
        """The forgery itself: a bare header, no Authorization at all."""
        ident = await resolve_websocket_identity(_ws({"x-tenant-id": CUSTOMER_TENANT}))
        assert ident.outcome is Outcome.NO_CREDENTIAL
        assert ident.should_close is True
        # And it still hands the handler nothing to act on if it ignores the flag.
        assert ident.tenant_id is None

    async def test_a_handshake_with_no_headers_at_all_must_close(self):
        ident = await resolve_websocket_identity(_ws({}))
        assert ident.should_close is True

    async def test_a_refused_handshake_still_closes(self, monkeypatch):
        """The pre-1.15.0 arm must not regress while the new one is added."""
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", OTHER_SUBJECT)
        with _introspection(_licence()):
            ident = await resolve_websocket_identity(
                _ws({"authorization": "Bearer gw", "x-tenant-id": CUSTOMER_TENANT})
            )
        assert ident.outcome is Outcome.REFUSED
        assert ident.should_close is True

    async def test_a_resolved_handshake_must_not_close(self):
        """The green half. Without it, `should_close = True` passes everything
        above and takes every legitimate socket down with it."""
        with _introspection(_licence()):
            ident = await resolve_websocket_identity(_ws({"authorization": "Bearer gw"}))
        assert ident.outcome is Outcome.RESOLVED
        assert ident.should_close is False

    async def test_an_allowlisted_on_behalf_handshake_must_not_close(self, monkeypatch):
        """The other green half: the shape coding-gateway and fr actually send."""
        monkeypatch.setenv("CODING_ONBEHALF_SUBJECTS", SERVICE_SUBJECT)
        with _introspection(_licence()):
            ident = await resolve_websocket_identity(
                _ws({"authorization": "Bearer gw", "x-tenant-id": CUSTOMER_TENANT})
            )
        assert ident.should_close is False
        assert ident.tenant_id == CUSTOMER_TENANT

    async def test_every_outcome_except_resolved_closes(self):
        """Derived from the enum, not hand-listed, so a member added later is
        covered the moment it exists.

        `should_close` is written as `outcome is not RESOLVED` for the same
        reason: a new member is a new way of *not* proving an identity and must
        fail CLOSED. Enumerating the refusing side would admit it silently,
        which is exactly how this hole stayed open.
        """
        non_resolved = [o for o in Outcome if o is not Outcome.RESOLVED]
        assert non_resolved, "positive control: the enum must have refusing members"
        assert len(non_resolved) == len(list(Outcome)) - 1
        for outcome in non_resolved:
            assert WebSocketIdentity(outcome=outcome).should_close is True, outcome
        assert WebSocketIdentity(outcome=Outcome.RESOLVED).should_close is False

    async def test_the_close_reason_is_safe_to_put_in_a_close_frame(self):
        """Handlers echo `reason` into the 1008 close frame, which is visible to
        whoever sent the assertion — it must never confirm the guess."""
        ident = await resolve_websocket_identity(_ws({"x-tenant-id": CUSTOMER_TENANT}))
        assert ident.reason
        assert CUSTOMER_TENANT not in ident.reason
