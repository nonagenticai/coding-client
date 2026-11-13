"""Identity resolution for WebSocket handshakes.

``AuthMiddleware`` is a ``BaseHTTPMiddleware``, and Starlette never invokes
``dispatch`` on a ``websocket`` scope. So **no flip and no middleware can close a
WebSocket route** — every WS handler has to resolve identity itself, explicitly.
That is why this module exists and why it is a plain function rather than
middleware: middleware is precisely the thing that does not run here.

The consequence is sharp. Once the HTTP paths stopped trusting a bare
``X-Tenant-Id`` (``TRUST_TENANT_HEADER=false``), the WS handlers became the only
remaining place in the fleet where a pod could assert any tenant and be believed.

The rule mirrors the HTTP one exactly
-------------------------------------
Same three-way decision as :func:`.._onbehalf.resolve_tenant_assertion`, for the
same reasons:

* no asserted header — the tenant is the one the caller's own licence names;
* asserted and **equal** — a no-op (this is what a proxy re-injecting the tenant
  it resolved from that same token looks like);
* asserted and **differing** — honoured only when the licence's ``subject_id`` is
  allowlisted, otherwise refused.

An uncredentialed handshake is now closed (1.15.0)
--------------------------------------------------
A browser cannot set an ``Authorization`` header on a WebSocket handshake — the
WebSocket API has no way to pass one. Browser-originated sockets therefore reach
a backend through a server-side proxy, and it is the PROXY that must present a
credential. Until every proxy had been converted, requiring one unconditionally
would not have hardened the browser path, it would simply have broken it. So
until 1.15.0 ``Outcome.NO_CREDENTIAL`` did **not** set
:attr:`WebSocketIdentity.should_close`: the handler fell back to a raw
``X-Tenant-Id`` read and logged a WARNING naming the peer.

That fallback was never a safety property, it was an *instrument* — the WARNING
existed to find the callers still to convert, and it has now reported. Over the
full log retention on both consumers (~10.5h on coding-realtime, ~18h on
coding-analysis) the WARNING fired 5 times on coding-realtime, every one of them
from ``peer=127.0.0.1`` — a verification probe — and 0 times on coding-analysis.
No real caller has ever used it. Meanwhile both legitimate callers now present a
credential: coding-gateway attaches its own licence on WS upgrades, and ``fr``
presents ``svc-fr-backend``'s licence on both of its WS proxies (driven live:
101 with auth, 403 without).

With the instrument's reading in, the residual is closed. A handshake carrying no
verifiable credential cannot name a tenant, so serving it is an authorisation
failure exactly as a refusal is, and ``should_close`` is True for both. The
``Outcome`` enum stays three-valued on purpose: REFUSED ("a credential, but not
for that tenant") and NO_CREDENTIAL ("no credential at all") are different
operational facts and want different log lines. Only the *decision* is now shared.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto

from ._onbehalf import forwarded_license_id, resolve_tenant_assertion
from .middleware import _user_from_license

logger = logging.getLogger(__name__)

__all__ = ["Outcome", "WebSocketIdentity", "resolve_websocket_identity"]

#: WS close code for a policy violation. 1008 is the protocol's own
#: "policy violation", which is what an authorisation refusal is.
POLICY_VIOLATION = 1008


class Outcome(Enum):
    """What the handshake proved, and therefore what the handler may do."""

    #: A licence was verified. ``tenant_id`` is authoritative.
    RESOLVED = auto()
    #: A licence was verified but it may not act for the tenant it asserted.
    #: The handler MUST close; serving this connection is a cross-tenant read.
    REFUSED = auto()
    #: No ``Authorization`` at all, or one that did not introspect to a live
    #: licence. Nothing was proved, so nothing may be served: the handler MUST
    #: close, same as REFUSED. Kept distinct from REFUSED because the two are
    #: different operational facts worth different log lines — see the module
    #: docstring for the measurement that made closing this safe.
    NO_CREDENTIAL = auto()


@dataclass(frozen=True)
class WebSocketIdentity:
    """The result of resolving a handshake. Immutable so a handler cannot
    accidentally widen it after the decision has been made."""

    outcome: Outcome
    tenant_id: str | None = None
    subject_id: str | None = None
    license_id: str | None = None
    #: Human-readable, safe to put in a WS close reason. Never contains the
    #: asserted tenant — echoing it back confirms the guess to an attacker.
    reason: str | None = None

    @property
    def should_close(self) -> bool:
        """True when serving this connection would be an authorisation failure.

        Both non-RESOLVED outcomes qualify, and the test is written as "not
        RESOLVED" rather than a list of the two so that a fourth outcome added
        later fails CLOSED by default: a new member is a new way of *not*
        proving an identity, and enumerating the refusing side would silently
        admit it.
        """
        return self.outcome is not Outcome.RESOLVED


async def resolve_websocket_identity(websocket) -> WebSocketIdentity:
    """Resolve who is on the other end of *websocket*.

    Takes the Starlette ``WebSocket`` rather than a ``Request``: both expose
    ``.headers`` and ``.url``, which is all the shared decision function reads, so
    the HTTP and WS paths run the *same* code and cannot drift.

    Never raises. A handshake is either resolved, refused, or credential-less.
    """
    user = await _user_from_license(websocket)

    if user is None:
        return WebSocketIdentity(
            outcome=Outcome.NO_CREDENTIAL,
            reason="no verifiable credential on the handshake",
        )

    effective_tenant, refused = resolve_tenant_assertion(
        websocket,
        subject_id=user.sub,
        token_tenant=user.tenant_id or "",
    )

    if refused:
        return WebSocketIdentity(
            outcome=Outcome.REFUSED,
            subject_id=user.sub,
            reason="this credential may not act for the tenant it asserted",
        )

    return WebSocketIdentity(
        outcome=Outcome.RESOLVED,
        tenant_id=effective_tenant,
        subject_id=user.sub,
        license_id=forwarded_license_id(websocket),
    )
