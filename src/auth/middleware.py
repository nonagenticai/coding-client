"""Authentication middleware - extracts user from Istio-forwarded headers.

Identity sources, in the order ``AuthMiddleware.dispatch`` tries them:

1. ``DEV_API_KEY`` / ``TEST_API_KEY`` — only when ``ENVIRONMENT`` is
   ``development`` or ``testing``. Never a production path.
2. ``X-User-Id`` / ``X-Tenant-Id`` / ``X-User-Roles`` — unverified *claims*,
   trustworthy only through the mesh edge. Gated on ``TRUST_TENANT_HEADER``
   (see :mod:`._header_trust`).
3. ``Authorization: Bearer <license>`` — verified by license introspection
   against ``LICENSE_INTROSPECT_URL``. This is the only source in the list that
   the library can actually *verify*.
4. Trusted-network bypass: a source inside ``TRUSTED_CIDRS`` with none of the
   above is allowed with a default tenant context. ``TRUSTED_CIDRS`` is **empty
   by default** — see :mod:`._trusted_networks` for why.

Anything else is a 401.

⚠️ Step 3 did not exist before 1.10.0, and its absence is what made
``TRUST_TENANT_HEADER=false`` unusable. With the gate off, step 2 yields nothing
and the chain went straight to step 4 — which is empty on all nine ``coding-*``
services — so **every** authenticated request 401'd, including ones carrying a
perfectly valid license. coding-realtime hit exactly that live: it has the gate
off in ``coding-realtime-config`` and was rejecting coding-gateway's
``GET /api/stats`` with "Unauthenticated request from untrusted network" while
the Bearer sat unread in the request. The edge EnvoyFilter strips nine identity
headers but never ``authorization``, and coding-gateway's ``_HOP_BY_HOP`` list
holds ``proxy-authorization`` but not ``authorization``, so the credential is
present at the pod. Nothing looked at it.

This module deliberately does NOT own an introspection implementation. It calls
:func:`.tenant._introspect_license` — same function, same caches: the 5-minute
positive one and the short negative one that keeps a rejected caller from being
a 1:1 amplifier into ``licenses`` (see the cache comment in ``tenant.py``). A
second copy of the rule is how ``TRUSTED_CIDRS`` and ``DEFAULT_TENANT_ID`` ended
up as byte-identical blocks here and in ``tenant.py``, where fixing one left the
other permissive.
"""

import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Single source of truth — TRUSTED_CIDRS and DEFAULT_TENANT_ID used to be
# byte-identical copies of the blocks in tenant.py, so a fix to one would have
# left the other permissive. DEFAULT_TENANT_ID is re-exported for back-compat.
from ._default_tenant import (
    DEFAULT_TENANT_ID,  # noqa: F401
    resolve_default_tenant,
)
from ._header_trust import trust_tenant_header
from ._onbehalf import resolve_tenant_assertion
from ._trusted_networks import TRUSTED_NETWORKS
from ._trusted_networks import is_trusted_network as _is_trusted_network
from .models import User

# The one introspection implementation and the one cache. Imported rather than
# reimplemented — see the module docstring. Importing it here also means the
# existing `patch("coding_client.auth.tenant.httpx.AsyncClient")` test double
# keeps intercepting the middleware path too: the call still executes in
# tenant.py's namespace.
#
# Who relies on that, measured 2026-10-01 with
# `git grep -c 'coding_client.auth.tenant.httpx' origin/main -- '*.py'` over
# every coding-* repo (an earlier revision of this comment named "the conftests
# of coding-testing / coding-ai / coding-analysis", which was wrong):
#   coding-analysis  tests/conftest.py, tests/unit/test_auth_middleware_and_deps.py,
#                    tests/unit/test_ws_identity.py
#   coding-realtime  tests/conftest.py, tests/unit/test_ws_identity.py
#   coding-testing   tests/unit/test_auth.py, tests/unit/test_middleware.py,
#                    tests/unit/test_fork_vouching.py
# coding-ai has ZERO: it patches `coding_client.auth.middleware._introspect_license`
# itself (tests/conftest.py, tests/unit/test_coverage_gaps.py,
# tests/unit/test_tenant_header_trust.py) — a double of the FUNCTION's binding
# in THIS module, so it never reaches tenant.py's httpx call. Re-measure before
# trusting a list.
from .tenant import _introspect_license

__all__ = ["AuthMiddleware", "PUBLIC_PATHS", "TRUSTED_NETWORKS"]

logger = logging.getLogger(__name__)

# DEFAULT_TENANT_ID is re-exported above from ._default_tenant and is ``None``
# when unset. It used to be ``os.getenv("DEFAULT_TENANT_ID", "n8n-dev")`` here,
# a byte-identical copy of the block in tenant.py — so the synthetic users
# minted below carried a tenant literal that nobody configured. Always go
# through ``resolve_default_tenant()``: unset means "do not mint a user".


# Paths that do not require authentication
PUBLIC_PATHS = frozenset(
    {
        "/",
        "/health",
        "/health/",
        "/health/ready",
        "/health/live",
        "/ready",
        "/metrics",
        "/openapi.json",
        "/docs",
        "/docs/",
        "/redoc",
    }
)


async def _user_from_license(request: Request) -> User | None:
    """Mint a :class:`User` from a verified ``Authorization: Bearer <license>``.

    Returns ``None`` — never raises, never a partially-trusted user — whenever
    the request cannot be shown to carry a live license. Every ``None`` below
    ends as a 401 in :meth:`AuthMiddleware.dispatch`, so the failure modes are
    deliberately indistinguishable to the caller:

    * no ``Authorization`` header, or one that is not a Bearer;
    * an empty token after the scheme;
    * ``LICENSE_INTROSPECT_URL`` unset — ``_introspect_license`` logs at ERROR
      and returns ``None`` rather than raising (tenant.py:81-83). An unset URL
      means "this path yields no identity". It must never mean "admit", and it
      must never mean "crash": a misconfigured Deployment is an outage for
      licensed callers, not a hole for unlicensed ones;
    * introspection failed, timed out, or the endpoint was unreachable —
      ``_introspect_license`` already swallows those into ``None``; the
      ``except`` below is the belt to that braces, so a raising introspection
      is a 401 and not a 500;
    * the license is inactive/expired (``active`` falsy);
    * the license body is malformed — a non-dict, or a ``tenant_id`` /
      ``subject_id`` that is not a string. See :func:`_user_from_license_data`;
    * the license is live but carries no usable ``tenant_id``. There is nothing
      to scope the caller's data to, and ``User.model_post_init`` would silently
      backfill the tenant from ``sub`` — a tenant named after the subject. Nine
      services would then read and write under it. Reject instead.

    ⚠️ The ``try`` below covers the whole parse, not just the HTTP call. The
    first revision of this function wrapped ``_introspect_license`` alone and
    left the ``User(...)`` build outside it, so a ``tenant_id`` of ``123`` raised
    a pydantic ``ValidationError`` straight out of ``dispatch`` as a **500** —
    while this docstring's first line claimed the function never raises. Whoever
    influences what the introspection endpoint returns must not get a liveness
    lever, and a 500 is not a rejection anybody audits.

    This runs *below* the identity-header block on purpose, mirroring the
    precedence chain documented in :mod:`.tenant`: header first (when trusted),
    license second. So with ``TRUST_TENANT_HEADER`` unset or true, a
    header-bearing request is served exactly as it was before 1.10.0 and this
    function is never reached — the change is additive, not a re-ordering.
    """
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return None

    token = auth_header[7:].strip()
    if not token:
        return None

    try:
        license_data = await _introspect_license(token)
        return _user_from_license_data(license_data)
    except Exception as exc:
        # Fail CLOSED. _introspect_license contains its own try/except around
        # the HTTP call, and _user_from_license_data type-checks every field it
        # feeds to the model, so reaching here means something we did not
        # anticipate — which is exactly when a 500 would be worst. The
        # `_user_from_license_data` call is INSIDE this block on purpose: that
        # is the structural guarantee, not the type checks, which only cover the
        # shapes `User` rejects today.
        logger.warning("License introspection raised; rejecting request: %s", exc)
        return None


def _user_from_license_data(license_data: dict | None) -> User | None:
    """Turn an introspection body into a :class:`User`, or ``None`` to reject.

    Split out of :func:`_user_from_license` so the whole parse — including the
    model construction — runs inside that function's ``try``.

    The annotation is ``_introspect_license``'s declared return type; the
    ``isinstance`` below is the runtime belt, because that declaration is only
    as good as ``resp.json()`` — a licenses endpoint answering ``200`` with a
    bare string or list would otherwise be an ``AttributeError`` on ``.get``.

    Every field is type-checked before it reaches the model. ``User.tenant_id``
    is ``str | None`` and ``User.sub`` is a required ``str``, so a non-string in
    either slot is a pydantic ``ValidationError``; and pydantic's lax mode would
    silently coerce ``b"subject"`` into ``"subject"``, minting a subject nobody
    issued. Neither is a shape the licenses service can produce — its
    ``TokenIntrospectResponse`` types both as ``str | None`` — so anything else
    means we are not talking to the licenses service, and the safe reading of
    that is "no identity".
    """
    if not isinstance(license_data, dict) or not license_data.get("active"):
        return None

    # `tenant_id` is the tenant (workspace/org) the licenses service resolves
    # for X-Tenant-Id injection. `subject_id` is the USER and must NEVER be used
    # for tenant scoping — the same distinction tenant.py:264-266 pins down.
    #
    # STRIP before testing. `if not tenant_id:` alone was a hole: "   " is
    # truthy, so it passed this guard, and then models.py:40 does
    # `if not (self.tenant_id or "").strip()` and backfilled the tenant from
    # `sub`. A payload of {"active": true, "tenant_id": "   ",
    # "subject_id": "attacker-sub"} was served 200 with tenant_id
    # "attacker-sub" — the guard's own failure mode, reached through the guard.
    # `.strip()` is the repo-wide convention for this: _default_tenant.
    # load_default_tenant_id() and models.py:40 both use it, and it treats
    # U+00A0 NO-BREAK SPACE as whitespace like the rest of them.
    raw_tenant = license_data.get("tenant_id")
    tenant_id = raw_tenant.strip() if isinstance(raw_tenant, str) else ""
    if not tenant_id:
        logger.warning(
            "License is active but carries no usable tenant_id (type=%s); rejecting "
            "rather than letting the tenant be backfilled from the subject.",
            type(raw_tenant).__name__,
        )
        return None

    # A missing/blank subject is normal and handled below with a marker. A
    # subject of the WRONG TYPE is not: it means the body is not the shape we
    # understand, so reject rather than coerce.
    raw_subject = license_data.get("subject_id")
    if raw_subject is not None and not isinstance(raw_subject, str):
        logger.warning(
            "License introspection returned a non-string subject_id (type=%s); "
            "rejecting rather than coercing it into the `sub` slot.",
            type(raw_subject).__name__,
        )
        return None

    # Roles: a licensed caller gets NO roles today, and that is correct.
    #
    # Measured, not assumed — the licenses service's introspect response is a
    # Pydantic `TokenIntrospectResponse` (licenses/main.py:497-512), so extra
    # keys are stripped on the wire, and the model has no `roles`, `scopes`,
    # `permissions`, `realm_access` or `entitlements` field. Its only
    # entitlement-shaped members are rate limits and quotas under `plan`. A
    # license says WHICH TENANT you are, never WHAT YOU MAY DO. The fleet's own
    # ext_authz agrees: license-authz builds `x-caller-roles` from a separate
    # Keycloak service-account JWT (license-authz/src/main.py:890-947), never
    # from the introspection body.
    #
    # So the read below is a tolerant parse, NOT a promise that roles arrive.
    # It is written down because two services already got this wrong in the
    # other direction — mlx_ingestion_backend/src/auth/middleware.py:193-199 and
    # scientific_processor/src/auth/middleware.py:410-420 both do
    # `data.get("roles", [])` under a docstring claiming "roles come only from
    # an introspected license". They are permanently empty and the docstring is
    # false. Here the empty case is the DOCUMENTED one: no roles means
    # `User.is_admin()` is False and `require_same_tenant` confines the caller
    # to the tenant its license named, which is the outcome we want. Never
    # substitute a default like ["user"] — that would hand a capability to
    # every licensed caller that no authority granted.
    raw_roles = license_data.get("roles")
    roles = (
        [r for r in raw_roles if isinstance(r, str) and r] if isinstance(raw_roles, list) else []
    )

    # `sub` is required by the model and is consulted by
    # `User.model_post_init` / `effective_tenant_id` as a LAST-RESORT tenant. It
    # cannot be left blank. When the license names no subject we use a marker
    # that is obviously not a Keycloak subject id (which is a bare uuid4 — never
    # prefixed, never containing a colon), so it can never be mistaken for one
    # downstream; `tenant_id` above is non-blank AFTER stripping, so this value
    # never reaches the tenant slot regardless. The `license:` prefix is the
    # asserted contract, not decoration — see
    # test_missing_subject_id_uses_the_license_marker_not_an_invented_subject.
    subject_id = (raw_subject or "").strip() or f"license:{tenant_id}"

    logger.debug("Authenticated via license introspection: tenant=%s", tenant_id)
    return User(
        sub=subject_id,
        preferred_username=subject_id,
        tenant_id=tenant_id,
        realm_access={"roles": roles},
    )


class AuthMiddleware(BaseHTTPMiddleware):
    """Extract user info from Istio-forwarded headers or API key."""

    async def dispatch(self, request: Request, call_next):
        # Skip auth for public endpoints
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        user = None

        # Check for development mode API key authentication
        environment = os.getenv("ENVIRONMENT", "production")
        is_dev_or_test = environment in ("development", "testing")

        if is_dev_or_test:
            # Check for Bearer token in Authorization header
            auth_header = request.headers.get("authorization", "")
            if auth_header.lower().startswith("bearer "):
                token = auth_header[7:].strip()
                dev_api_key = os.getenv("DEV_API_KEY", "")
                test_api_key = os.getenv("TEST_API_KEY", "")

                if (dev_api_key and token == dev_api_key) or (
                    test_api_key and token == test_api_key
                ):
                    # The dev API key proves nothing about *which tenant* the
                    # caller is. Without a configured DEFAULT_TENANT_ID there is
                    # no answer, so the key does not authenticate: `user` stays
                    # None and the request falls through to the header/trusted-
                    # network branches and ultimately to a 401.
                    dev_tenant = resolve_default_tenant(
                        f"{environment}-mode API key authentication"
                    )
                    if dev_tenant is not None:
                        logger.debug("API key authentication successful in %s mode", environment)
                        user = User(
                            sub="dev-user",
                            preferred_username="dev-user",
                            email="dev@example.com",
                            tenant_id=dev_tenant,
                            organization_id="dev-org",
                            realm_access={"roles": ["admin", "developer"]},
                        )

        # Fall back to Istio headers if no API key auth.
        #
        # "Istio headers" is the optimistic name for them. At the mesh edge they
        # are injected by ext_authz from a validated license and are genuinely
        # trustworthy; pod-to-pod they are whatever the caller typed, and this
        # block turns them into an authenticated User — tenant AND roles. Gated
        # on TRUST_TENANT_HEADER (see ._header_trust); with the gate off the
        # request is treated as carrying no identity at all and falls through to
        # the trusted-network check and then a 401.
        if user is None:
            trust_headers = trust_tenant_header()
            roles = (
                [r for r in request.headers.get("x-user-roles", "").split(",") if r]
                if trust_headers
                else []
            )
            x_user_id = request.headers.get("x-user-id") if trust_headers else None
            x_tenant_id = request.headers.get("x-tenant-id") if trust_headers else None

            if x_user_id or x_tenant_id:
                user = User(
                    sub=x_user_id or "anonymous",
                    preferred_username=request.headers.get("x-user-name", "anonymous"),
                    email=request.headers.get("x-user-email"),
                    tenant_id=x_tenant_id,
                    organization_id=request.headers.get("x-organization-id"),
                    realm_access={"roles": roles},
                )

        # Fall back to license introspection — the only VERIFIED identity source
        # in this chain (see _user_from_license and the module docstring).
        #
        # This block is why the whole file changed. It used to be the `else:` of
        # the header check above, meaning: no identity header => straight to the
        # trusted-network bypass. With TRUST_TENANT_HEADER=false that made the
        # header branch unreachable AND left nothing between it and a bypass
        # that is disabled on every service, so a valid Bearer 401'd. Ordering
        # matters both ways: it sits BELOW the header block so nothing changes
        # while the gate is on, and ABOVE the network bypass so a real license
        # beats a CIDR guess.
        if user is None:
            user = await _user_from_license(request)

            # On-behalf-of. A service acting for a customer presents its OWN
            # license and names the customer in a plain X-Tenant-Id; the
            # assertion is honoured only when the license's subject is
            # allowlisted (see ._onbehalf for the disagreement rule and why it
            # is not keyed on the header's mere presence).
            #
            # This sits INSIDE the license branch, not below it as a fifth arm.
            # Below, it would be unreachable: _user_from_license has already
            # succeeded and minted a User scoped to the SERVICE's own tenant, so
            # a later arm would never run and every S2S call would silently
            # resolve to the caller's tenant instead of the customer's — the
            # data-scoping bug this feature exists to avoid, shipped as the fix.
            #
            # `user.sub` IS the introspected subject_id (or the `license:`
            # marker, which ._onbehalf refuses), and `user.tenant_id` is the
            # tenant the token names, so no second introspection is needed.
            if user is not None:
                effective_tenant, refused = resolve_tenant_assertion(
                    request,
                    subject_id=user.sub,
                    token_tenant=user.tenant_id or "",
                )
                if refused:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": "TENANT_ASSERTION_NOT_PERMITTED",
                            "detail": (
                                "This credential may not assert a tenant other than the "
                                "one its license names."
                            ),
                        },
                    )
                if effective_tenant != user.tenant_id:
                    # `effective_tenant_id` is a read-time property over
                    # `tenant_id`, so replacing that one field is enough and no
                    # re-derivation is needed. `model_copy` rather than mutation
                    # so a caller holding the old object keeps seeing the tenant
                    # it was authenticated as.
                    user = user.model_copy(update={"tenant_id": effective_tenant})
                    # The audit trail (`vouching_subject_id`, `license_id`) and
                    # the `tenant_vouched` flag are set by
                    # `resolve_tenant_assertion` itself, on every path — this arm
                    # used to set them here and the other two resolvers did not,
                    # so a WebSocket route (which only ever runs `require_tenant`)
                    # carried no attribution at all.

        if user is None:
            # No identity from any verifiable source - check trusted network.
            # The bypass needs BOTH a configured network and a configured tenant
            # to grant; with no DEFAULT_TENANT_ID we reject rather than mint a
            # synthetic user against a literal nobody chose.
            client_host = request.client.host if request.client else None
            default_tenant = (
                resolve_default_tenant("the trusted-network bypass in AuthMiddleware")
                if _is_trusted_network(client_host)
                else None
            )
            if default_tenant is not None:
                user = User(
                    sub=default_tenant,
                    preferred_username="internal",
                    tenant_id=default_tenant,
                )
            else:
                # Untrusted network (or no tenant configured) - reject
                logger.warning(
                    "Unauthenticated request from untrusted network: %s %s",
                    request.method,
                    request.url.path,
                )
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Authentication required"},
                )

        request.state.user = user
        return await call_next(request)
