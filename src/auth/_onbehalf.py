"""On-behalf-of vouching: who may assert a tenant that is not their own.

A `coding-*` service that calls a sibling has, until now, had no way to say
*"I am the containers service, and I am acting for customer T"*. Every outbound
call carries a bare ``X-Tenant-Id`` and nothing else — a census of the fleet
found **zero** sites forwarding an inbound ``Authorization``. So the only way a
sibling call could succeed was through header trust, which is precisely the hole
``TRUST_TENANT_HEADER=false`` exists to close. Flipping the gate without this
module turns working service-to-service calls into 401s.

Handing each service its own license does not solve it either: the tenant comes
from the introspection body, so every S2S call would silently resolve to the
*calling service's* tenant. That is a data-scoping bug wearing a fix's clothes.

The mechanism
-------------
A caller presents its **own** service license in ``Authorization: Bearer`` and
names the **customer** tenant in a plain ``X-Tenant-Id``. The asserted tenant is
honoured only when the license introspects to a ``subject_id`` on this
allowlist. This is the fleet-standard shape — ``kag_graph_service``,
``graph_adapter_service``, ``kag`` and ``kag_orchestrator`` all run it, keyed on
the same ``subject_id`` that ``licenses/scripts/provision_service_token.py``
prints when it mints the credential.

Unlike KAG — which copy-pastes the gate into seven services because they share
no framework layer — every ``coding-*`` service consumes this one SDK, so the
rule lives here once.

Why the decision keys on DISAGREEMENT, not on the header's presence
-------------------------------------------------------------------
The obvious rule, "a plain ``X-Tenant-Id`` is honoured iff vouched, else 403",
would break the entire north-south path. ``coding-gateway`` forwards the
client's ``Authorization`` verbatim (its ``_HOP_BY_HOP`` list holds
``proxy-authorization`` but **not** ``authorization``) *and* injects its own
resolved ``x-tenant-id``. So every browser-originated request already arrives
carrying both headers — the vouching shape, on the wire today, with nothing
evaluating it. Under the naive rule the gateway's own injection would be
indistinguishable from a forgery and every request behind it would 403.

The tenant the gateway injects is the one it resolved from that same license, so
it *agrees* with the token. Refusing only on disagreement keeps that path intact
while still closing forgery:

===========================  =========  ==========================================
asserted vs token's tenant   vouched?   outcome
===========================  =========  ==========================================
absent                       --         token's tenant (unchanged behaviour)
equal                        --         token's tenant (the gateway's own inject)
differs                      yes        the **asserted** tenant — the grant
differs                      no         **403** ``TENANT_ASSERTION_NOT_PERMITTED``
===========================  =========  ==========================================

Fail-closed, and the allowlist IS the rollout lever
---------------------------------------------------
Unset or empty vouches for nobody, which makes this module inert on install:
with no allowlist, a differing assertion can only ever be refused, and today
every such request is already refused by ``TRUST_TENANT_HEADER=false`` (or
accepted wholesale when the gate is on, in which case this code is never
reached). There is deliberately **no permissive spelling** — no wildcard, no
"allow all", no escape-hatch variable. The fleet's own doctrine, written into
the karma Deployment: *"an empty list is the fail-safe"*.

That also makes this safer than the boolean it complements.
``TRUST_TENANT_HEADER`` fails **open** on a typo — ``"flase"`` logs an error and
keeps trusting. A typo in an allowlist entry can only ever fail to match.
"""

import logging
import os
import uuid

from starlette.requests import HTTPConnection

logger = logging.getLogger(__name__)

#: Comma-separated ``subject_id``s permitted to assert a tenant that is not the
#: one their own license names. The value is what
#: ``licenses/scripts/provision_service_token.py`` prints as ``subject_id``.
ENV_VAR = "CODING_ONBEHALF_SUBJECTS"

#: Marker prefix the middleware synthesises for a license that names no subject
#: (``license:<tenant_id>``). It is not a subject anyone was issued, so it must
#: never be allowlistable — see :func:`onbehalf_subjects`.
_SYNTHETIC_SUBJECT_PREFIX = "license:"

_warned_synthetic: set[str] = set()


def onbehalf_subjects() -> frozenset[str]:
    """Parse the allowlist. Read at call time so tests and rollouts can move it.

    Entries are stripped and blanks dropped, so trailing commas and wrapped YAML
    are harmless.

    🔴 A ``license:``-prefixed entry is **rejected**, loudly and every time.
    When an active license carries no ``subject_id`` the middleware substitutes
    the marker ``license:<tenant_id>`` so the blank never reaches the ``sub``
    slot. That marker is shared by *every* subject-less license issued for that
    tenant, so allowlisting one would hand the vouch to all of them at once —
    the allowlist would stop naming a service and start naming a crowd. There is
    no legitimate reason to list one, so this is a hard reject rather than a
    warning: dropping the entry fails closed, honouring it fails open.
    """
    raw = os.getenv(ENV_VAR, "")
    subjects: set[str] = set()

    for entry in raw.split(","):
        subject = entry.strip()
        if not subject:
            continue
        if subject.startswith(_SYNTHETIC_SUBJECT_PREFIX):
            if subject not in _warned_synthetic:
                _warned_synthetic.add(subject)
                logger.error(
                    "%s contains the synthetic marker %r, which is not a real subject and "
                    "is shared by every subject-less license for that tenant. Ignoring it. "
                    "Use the subject_id printed by provision_service_token.py.",
                    ENV_VAR,
                    subject,
                )
            continue
        subjects.add(subject)

    return frozenset(subjects)


def asserted_tenant(request: HTTPConnection) -> str:
    """The tenant the caller is asking to act for, or ``""`` if none.

    Read **ungated**. ``AuthMiddleware`` and ``require_tenant`` both null their
    own ``x-tenant-id`` read when ``trust_tenant_header()`` is false; reusing
    that value here would make vouching dead in exactly the deployment posture it
    exists for.

    A ``Bearer``-shaped value is treated as absent. Some fleet services overload
    ``X-Tenant-Id`` to carry a credential (``coding-ai``'s worker-manager client
    does), and binding a tenant literally named ``"Bearer"`` would be a smuggling
    path. The split-on-whitespace form catches ``"Bearer  tok"`` and
    ``"Bearer\\ttok"``, which a ``startswith("Bearer ")`` test does not.
    """
    raw = (request.headers.get("x-tenant-id") or "").strip()
    if not raw:
        return ""

    parts = raw.split()
    if parts and parts[0].lower() == "bearer":
        return ""

    return raw


def may_vouch(subject_id: str | None) -> bool:
    """True iff ``subject_id`` is allowlisted to act for another tenant.

    Fail-closed at every exit: no subject, empty allowlist, synthetic marker, or
    simply not listed.
    """
    if not subject_id:
        return False
    if subject_id.startswith(_SYNTHETIC_SUBJECT_PREFIX):
        return False

    subjects = onbehalf_subjects()
    if not subjects:
        return False

    return subject_id in subjects


#: Attributes this module writes onto ``request.state`` on EVERY path, so a
#: reader can distinguish "the resolver ran and did not vouch" from "the
#: resolver never ran". A reader that can only ever see the absence of an
#: attribute cannot tell those apart, and a guard satisfied by a reader that
#: never fires is not a guard.
STATE_VOUCHED = "tenant_vouched"
STATE_ASSERTED_TENANT = "asserted_tenant"
STATE_VOUCHING_SUBJECT = "vouching_subject_id"
STATE_LICENSE_ID = "license_id"


def _record_not_vouched(request: HTTPConnection) -> None:
    """Mark this request as *not* vouched. Called on both non-vouch exits."""
    request.state.tenant_vouched = False


def tenant_license_verified(request: HTTPConnection) -> bool:
    """True iff this request's tenant was resolved from a **verified licence**.

    False when it came from a trusted ``X-Tenant-Id`` header, from the
    trusted-network bypass, or from nowhere at all — none of which reach
    :func:`resolve_tenant_assertion`, which is why its absence is the signal.

    🔴 This is the question a service must ask before lending its own credential
    to an outbound call. ``coding-gateway`` presents its licence downstream so
    the callee will honour the tenant it injects; if that tenant came from an
    unverified header, the gateway is signing for a claim it never checked, and
    the callee's allowlist — which exists to police exactly this — is satisfied
    by the wrong party.

    That is not hypothetical. Driven live on 2026-08-14: a forged, credential-less
    ``x-tenant-id`` on a WebSocket upgrade to coding-gateway was accepted under
    header trust, the gateway attached its own allowlisted licence, and
    coding-analysis logged ``Vouched on-behalf-of: subject <svc-coding-gateway>
    asserted tenant <someone else's>``. Any pod could read any tenant. The gate
    below is what makes that impossible: with the tenant unverified, no
    credential is lent, and the callee refuses as it should.
    """
    return getattr(request.state, STATE_VOUCHED, None) is not None


def tenant_was_vouched(request: HTTPConnection) -> bool:
    """True iff this request's tenant came from an on-behalf-of vouch.

    The accessor exists so consumers do not hand-spell ``request.state``: a
    renamed attribute then breaks in one place instead of silently reading
    ``False`` forever at every call site. ``coding-gateway`` is the consumer —
    it decides whether to forward the caller's credential or substitute its own.

    **Defaults to False when the resolver never ran**, which is the safe answer:
    no vouch happened, so nothing about the outbound credential should change.
    That covers the header-trust, trusted-network and no-credential paths, none
    of which reach :func:`resolve_tenant_assertion` at all.
    """
    return bool(getattr(request.state, STATE_VOUCHED, False))


def resolve_tenant_assertion(
    request: HTTPConnection, *, subject_id: str | None, token_tenant: str
) -> tuple[str, bool]:
    """Apply the disagreement rule. Returns ``(tenant_to_use, refused)``.

    The single implementation of the table in this module's docstring. Both
    :class:`~.middleware.AuthMiddleware` and :func:`~.tenant.require_tenant`
    call it rather than each re-deriving the rule — the two have drifted before
    (``TRUSTED_CIDRS`` and ``DEFAULT_TENANT_ID`` were once byte-identical copies,
    and fixing one left the other permissive).

    When ``refused`` is true the caller must reject with **403**, not 401: the
    request is authenticated — the license is live and verified — it is simply
    not authorised to speak for that tenant. A 401 would invite the caller to
    retry with different credentials, which is not the problem.

    Tenants are compared case-insensitively. The equal-case exists to recognise
    ``coding-gateway`` re-injecting the tenant it resolved from this same token,
    and a casing difference there would produce a false 403 on the entire
    north-south path. It costs nothing: honouring a *differing* tenant still
    requires the allowlist, so this only widens what counts as "the same tenant",
    never who may change it.

    The outcome is also RECORDED on ``request.state`` (see ``STATE_*`` above),
    because a caller downstream of this decision has to act on it and cannot
    re-derive it. ``coding-gateway`` is that caller: it forwards the client's own
    credential when the tenant agreed, and substitutes its own when it had to
    vouch — because on a vouched call the client's credential names a *different*
    tenant than the one being asserted onward, which is precisely what the next
    hop refuses. Recording it here rather than at each call site is the same
    reason the rule itself lives here: ``AuthMiddleware``, ``require_tenant`` and
    ``optional_tenant`` have drifted apart before.
    """
    asserted = asserted_tenant(request)
    if not asserted or asserted.casefold() == token_tenant.casefold():
        _record_not_vouched(request)
        return token_tenant, False

    if not may_vouch(subject_id):
        logger.warning(
            "Refusing tenant assertion: subject %r is not in %s and asserted a tenant "
            "other than the one its license names (path=%s)",
            subject_id,
            ENV_VAR,
            request.url.path,
        )
        _record_not_vouched(request)
        return token_tenant, True

    logger.info(
        "Vouched on-behalf-of: subject %r asserted tenant %r (path=%s)",
        subject_id,
        asserted,
        request.url.path,
    )
    request.state.tenant_vouched = True
    request.state.asserted_tenant = asserted
    # Audit trail, and the attribution a vouched call must carry onward: the
    # CUSTOMER's license (forwarded by the caller), never the vouching service's
    # own — otherwise every customer's spend bills to the service. Set here for
    # all three resolvers; AuthMiddleware used to set these two itself, and
    # require_tenant / optional_tenant did not, so a WebSocket route (which only
    # ever runs require_tenant) had no attribution at all.
    request.state.vouching_subject_id = subject_id
    request.state.license_id = forwarded_license_id(request)
    return asserted, False


def forwarded_license_id(request: HTTPConnection) -> str | None:
    """The customer's ``X-License-Id``, or ``None`` if absent/malformed.

    On a vouched call the license that should be *attributed* is the customer's,
    forwarded by the caller — never the vouching service's own, which would bill
    every customer's spend to the service. Same rule as
    ``kag_orchestrator``'s vouched branch.

    Validated as a UUID and returned as the canonical string form, so a
    caller-controlled header cannot inject an arbitrary value into a field that
    downstream consumers treat as an identifier.
    """
    raw = (request.headers.get("x-license-id") or "").strip()
    if not raw:
        return None

    try:
        return str(uuid.UUID(raw))
    except ValueError:
        logger.warning("Ignoring malformed X-License-Id on a vouched request")
        return None
