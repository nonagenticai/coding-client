"""Tenant isolation middleware and dependencies.

This module provides:
1. TenantMiddleware - Extracts X-Tenant-Id header and sets it on the user
2. get_tenant_id dependency - For use in route handlers to get current tenant
3. require_tenant dependency - Ensures tenant_id is present
4. create_tenant_context - Creates TenantContext from request for service layer

Priority order for tenant extraction:
1. X-Tenant-Id header (from ext_authz if it arrives through ztunnel)
2. Authorization: Bearer <token> -> license introspection endpoint
3. User state fallback (for internal service-to-service calls)
4. Trusted-network bypass -> DEFAULT_TENANT_ID (TRUSTED_CIDRS, empty by default)

⚠️ Step 1 outranks step 2, and step 1 is an UNVERIFIED claim. A caller that can
reach the port pod-to-pod (which does not traverse the edge ext_authz filter
that would have stripped and re-injected the header) can assert any tenant and
be served it, without any license at all. ``TRUST_TENANT_HEADER=false`` turns
step 1 off for a service; see :mod:`._header_trust` for why the default leaves
it on. That gate applies to every place in this module that reads an identity
header — ``TenantMiddleware``, ``require_tenant``, ``optional_tenant``,
``get_current_user_with_tenant`` and ``create_tenant_context`` — and to
``AuthMiddleware`` in ``middleware.py``. They must be flipped together or a
service closes one route and leaves the neighbouring one forgeable.
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Callable
from typing import TYPE_CHECKING

import httpx
from cachetools import TTLCache
from fastapi import Depends, HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

# Single source of truth for both bypass knobs — TRUSTED_CIDRS (which callers
# may skip authentication) and DEFAULT_TENANT_ID (which tenant they are then
# granted). Both used to be byte-identical copies of blocks in middleware.py, so
# a fix to one would have left the other permissive.
#
# Both names are re-exported here for backward compatibility. 1.7.0 moved
# TRUSTED_NETWORKS to ._trusted_networks and dropped it from this module — but
# coding-security (src/auth/tenant.py:22) and coding-testing
# (src/auth/tenant.py:16) import the name from HERE. Both wrap their
# auth-middleware import in
# `except ImportError: logger.warning(... running WITHOUT authentication ...)`,
# so removing it did not fail their build — it would have made them start with
# NO auth middleware at all, announced only as a warning. A back-compat shim is
# the difference between a lockfile bump being a security fix and a total
# unauthenticated-access regression. Keep both until every importer moves to
# `coding_client.auth._trusted_networks` / `._default_tenant`.
from ._default_tenant import (
    DEFAULT_TENANT_ID,  # noqa: F401
    resolve_default_tenant,
)
from ._header_trust import trust_tenant_header
from ._onbehalf import resolve_tenant_assertion
from ._trusted_networks import TRUSTED_NETWORKS  # noqa: F401
from ._trusted_networks import is_trusted_network as _is_trusted_network
from .models import User

if TYPE_CHECKING:
    # TODO: service-specific import removed
    # from src.app.core.tenant_context import TenantContext
    pass

logger = logging.getLogger(__name__)

# Header name for tenant ID (set by Istio gateway after license validation)
TENANT_ID_HEADER = "X-Tenant-Id"

# License introspection caches.
#
# TWO objects, ONE implementation and ONE code path — cachetools gives a
# TTLCache a single ttl, and a granted decision and a refused one must expire on
# very different clocks. Everything that reads or writes either of them lives in
# `_introspect_license` below; use `clear_license_caches()` to empty them.
#
# Why the negative cache exists
# -----------------------------
# `_introspect_license` used to cache only when `data.get("active")`, so every
# refusal — revoked license, unknown token, licenses service down — was a fresh
# POST, and a fresh `httpx.AsyncClient`, therefore a fresh TCP connection, to
# `licenses:8544`. `licenses/main.py:820-827` calls
# that "the fleet's hottest auth path".
#
# That was harmless while nothing read the Authorization header. Once
# `AuthMiddleware._user_from_license` started introspecting (1.10.0), any
# unauthenticated caller that can reach a gate-off `coding-*` port became a 1:1
# amplifier into shared infrastructure: one garbage Bearer in, one POST out.
# Under a retry storm the amplified path is precisely the one every other
# service also needs to authenticate through.
#
# Why the TTLs are what they are
# ------------------------------
# 10s vs 300s. The negative window is the time a caller stays refused after
# their license is (re-)issued or the licenses service recovers, so it must be
# small. It is already strictly smaller than the risk accepted in the other
# direction: the positive cache honours a REVOKED license for up to 5 minutes.
# Non-zero, because zero is the 1:1 fan-out this exists to stop — 10s caps a hot
# loop at one outbound call per token per 10s.
#
# ⚠️ What this does NOT do, stated so the comment does not outrun the code: it
# dampens repeated presentations of the SAME token. A caller rotating tokens
# mints a fresh key every time and still fans out 1:1. The keys are therefore
# attacker-controlled, which is why `maxsize` is not optional — LRU eviction is
# the memory bound. Rate limiting at the edge is the answer to a rotating flood;
# this is not.
POSITIVE_CACHE_TTL_SECONDS = 300
NEGATIVE_CACHE_TTL_SECONDS = 10

_license_cache: TTLCache = TTLCache(maxsize=1000, ttl=POSITIVE_CACHE_TTL_SECONDS)
_negative_license_cache: TTLCache = TTLCache(maxsize=1000, ttl=NEGATIVE_CACHE_TTL_SECONDS)


def clear_license_caches() -> None:
    """Empty both introspection caches.

    Tests must clear BOTH or a refusal cached by one test leaks into the next
    and silently suppresses its outbound call. Provided as one function so no
    caller has to remember that there are two objects.
    """
    _license_cache.clear()
    _negative_license_cache.clear()


# LICENSE_INTROSPECT_URL is read from env at call time; production injects it
# via the Deployment env block (see the platform configuration policy).
#
# There is no default. When it is unset, introspection is SKIPPED and
# _introspect_license returns None — it does NOT raise. (An earlier comment here
# claimed "missing env raises at first introspection attempt"; it never did.
# Comment and behaviour disagreed, which is how three services ran without it
# unnoticed.) Skipping is now safe rather than permissive: with TRUSTED_CIDRS
# empty by default there is no *network* bypass left for the request to fall
# through to, and it is logged at ERROR below rather than WARNING.
#
# ⚠️ But this does NOT mean the request necessarily 401s. An earlier version of
# this comment claimed "there is no bypass left" — that is wrong, and the
# correction matters. `require_tenant` Priority 1/1b returns a bare, unverified
# `X-Tenant-Id` header BEFORE reaching license introspection at all, so on that
# path this ERROR is never even emitted. `require_tenant` is tenant *resolution*,
# not authentication; coding-github's routers/github_internal.py says the same.
# Header trust is only sound while the mesh restricts who can reach the port
# (gitops #2298 narrowed that for coding-*). Closing Priority 1b is tracked
# separately — do not read this module as "auth is now closed".
LICENSE_INTROSPECT_URL = os.getenv("LICENSE_INTROSPECT_URL", "")

# DEFAULT_TENANT_ID is re-exported above from ._default_tenant and is ``None``
# when unset — there is deliberately no literal default. It used to be
# ``os.getenv("DEFAULT_TENANT_ID", "n8n-dev")`` here AND, byte-identically, in
# middleware.py; see ._default_tenant for why that literal was a data-isolation
# bug rather than a harmless placeholder. Read it through
# ``resolve_default_tenant()``, never as a captured constant, so that "unset"
# means "reject the caller" at every site.


async def _introspect_license(token: str) -> dict | None:
    """Introspect a license token to get tenant context.

    Args:
        token: The license token (from Authorization header).

    Returns:
        License data dict with 'active', 'tenant_id' (the tenant/workspace — what
        X-Tenant-Id should carry) and 'subject_id' (the user; never the tenant), etc.
        Returns None if introspection fails or token is invalid.

    Both outcomes are cached — the grant for ``POSITIVE_CACHE_TTL_SECONDS``, the
    refusal for the much shorter ``NEGATIVE_CACHE_TTL_SECONDS``. See the comment
    above the two cache objects for why the refusal is cached at all.
    """
    cache_key = f"lic:{hashlib.sha256(token.encode()).hexdigest()[:16]}"
    if cache_key in _license_cache:
        return _license_cache[cache_key]
    if cache_key in _negative_license_cache:
        # The stored DECISION, replayed. Never "we already asked, fall through":
        # a refusal that degrades into no-answer would turn a fan-out fix into
        # an authentication bypass.
        return _negative_license_cache[cache_key]

    introspect_url = os.getenv("LICENSE_INTROSPECT_URL", LICENSE_INTROSPECT_URL)
    if not introspect_url:
        # ERROR, not WARNING: a license token was presented and we cannot verify
        # it, so this request WILL 401. That is a misconfiguration causing an
        # outage for every licensed caller, not a routine condition.
        #
        # Deliberately NOT negative-cached: no outbound call was made, so there
        # is no amplification to dampen, and caching would only delay recovery
        # once the env var is set.
        logger.error(
            "LICENSE_INTROSPECT_URL not set; cannot introspect the presented "
            "license token, so this request will be rejected. Set it on the "
            "Deployment env block."
        )
        return None

    data: dict | None = None
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.post(introspect_url, json={"token": token})
            if resp.status_code == 200:
                parsed = resp.json()
                # A 200 carrying something that is not an object is not a
                # license. Guarded here so callers never meet a non-dict.
                data = parsed if isinstance(parsed, dict) else None
    except Exception as e:
        logger.warning(f"License introspection failed: {e}")
        data = None

    if data is not None and data.get("active"):
        _license_cache[cache_key] = data
    else:
        _negative_license_cache[cache_key] = data
    return data


class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and validate tenant ID from headers.

    This middleware runs after AuthMiddleware and:
    1. Extracts X-Tenant-Id header (set by Istio after /license/introspect)
    2. Updates the user's tenant_id if header is present
    3. Logs tenant context for auditing

    Usage:
        app.add_middleware(TenantMiddleware)
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and extract tenant context."""
        # Extract tenant ID from header.
        # Gated on TRUST_TENANT_HEADER (see ._header_trust): when header trust is
        # off, the header is treated as absent, so request.state.tenant_id is
        # never populated from it and `require_tenant` falls through to license
        # introspection instead of returning an unverified claim.
        header_tenant_id = request.headers.get(TENANT_ID_HEADER) if trust_tenant_header() else None

        # If user is authenticated, update their tenant_id from header
        if hasattr(request.state, "user") and request.state.user:
            user: User = request.state.user

            if header_tenant_id:
                # Header takes precedence (set by Istio after license validation)
                user.tenant_id = header_tenant_id
                logger.debug(
                    "Tenant ID set from header: %s for user %s",
                    header_tenant_id,
                    user.preferred_username,
                )
            elif not user.tenant_id:
                # Fallback to user's sub if no tenant_id set
                user.tenant_id = user.sub
                logger.debug("Tenant ID defaulted to user sub: %s", user.tenant_id)

            # Store effective tenant_id in request state for easy access
            request.state.tenant_id = user.effective_tenant_id

        elif header_tenant_id:
            # No authenticated user but header present (service-to-service call)
            request.state.tenant_id = header_tenant_id
            logger.debug("Tenant ID from header (no user): %s", header_tenant_id)

        return await call_next(request)


def get_tenant_id(request: Request) -> str | None:
    """Get the current tenant ID from request state (sync version).

    This dependency can be used in route handlers to get the tenant ID
    for filtering database queries. For async with license introspection
    fallback, use require_tenant instead.

    Usage:
        @router.get("/items")
        async def list_items(tenant_id: str = Depends(get_tenant_id)):
            return await db.get_items_by_tenant(tenant_id)

    Returns:
        The tenant ID or None if not set.
    """
    return getattr(request.state, "tenant_id", None)


async def require_tenant(request: Request) -> str:
    """Require a tenant ID to be present with license introspection fallback.

    Priority:
        1. X-Tenant-Id header (from ext_authz if it arrives through ztunnel)
        2. Authorization: Bearer <token> -> license introspection
        3. User from request.state (internal service-to-service)

    Usage:
        @router.get("/protected")
        async def protected_endpoint(tenant_id: str = Depends(require_tenant)):
            return {"tenant_id": tenant_id}

    Returns:
        The tenant ID.

    Raises:
        HTTPException: If no tenant ID is found (401 Unauthorized).
    """
    # Priority 1: From request.state (set by middleware from X-Tenant-Id header)
    tenant_id = get_tenant_id(request)
    if tenant_id:
        return tenant_id

    # Priority 1b: Direct X-Tenant-Id header (works without TenantMiddleware,
    # e.g. when gateway forwards headers to a backend with ENABLE_AUTH=false).
    #
    # This is an UNVERIFIED claim and it sits above license introspection, so a
    # forged header beats having no license. It is sound only where the mesh
    # controls who can reach the port. Gated on TRUST_TENANT_HEADER; when off we
    # skip the block entirely and fall through to Priority 2 — the request is
    # NOT downgraded to DEFAULT_TENANT_ID.
    if trust_tenant_header():
        x_tenant_id = request.headers.get("x-tenant-id")
        if x_tenant_id:
            request.state.tenant_id = x_tenant_id
            return x_tenant_id

    # Priority 2: License introspection from Authorization header.
    #
    # The scheme test is case-INSENSITIVE and the token is stripped, matching
    # AuthMiddleware (middleware.py). These used to disagree: this function
    # required a literal "Bearer " and did not strip, so a lowercase `bearer`
    # authenticated through the middleware but was invisible here, and a route
    # using this dependency would 401 a request the middleware had just admitted.
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        license_data = await _introspect_license(token)
        if license_data and license_data.get("active"):
            # `tenant_id` is the tenant (workspace/org) claim the licenses service
            # returns for X-Tenant-Id injection; `subject_id` is the USER and must
            # NOT be used for tenant scoping.
            raw_tenant = license_data.get("tenant_id")
            tenant_id = raw_tenant.strip() if isinstance(raw_tenant, str) else ""
            if tenant_id:
                # On-behalf-of, same rule as AuthMiddleware and through the same
                # function so the two cannot drift. A service asserting another
                # tenant is honoured only when its subject is allowlisted; an
                # unvouched disagreement is a 403, not a silent downgrade to the
                # caller's own tenant.
                effective_tenant, refused = resolve_tenant_assertion(
                    request,
                    subject_id=(license_data.get("subject_id") or None),
                    token_tenant=tenant_id,
                )
                if refused:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            "This credential may not assert a tenant other than the one "
                            "its license names."
                        ),
                    )
                logger.debug(f"Tenant ID from license introspection: {effective_tenant}")
                # Cache in request state for subsequent calls
                request.state.tenant_id = effective_tenant
                return effective_tenant

    # Priority 3: Fallback to user state
    if hasattr(request.state, "user") and request.state.user:
        user: User = request.state.user
        tenant_id = user.effective_tenant_id
        if tenant_id:
            return tenant_id

    # Priority 4: Trusted network bypass.
    # Only usable when an operator configured BOTH the network (TRUSTED_CIDRS)
    # and the tenant it grants (DEFAULT_TENANT_ID). With no tenant configured we
    # fall through to the 401 below rather than inventing one.
    client_host = request.client.host if request.client else None
    if _is_trusted_network(client_host):
        default_tenant = resolve_default_tenant("the trusted-network bypass in require_tenant")
        if default_tenant is not None:
            request.state.tenant_id = default_tenant
            return default_tenant

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Tenant context required. Ensure X-Tenant-Id header is set or provide valid license token.",
    )


async def optional_tenant(request: Request) -> str | None:
    """Extract tenant ID if available, without requiring it.

    Same priority chain as ``require_tenant`` but returns *None* instead
    of raising 401 when no tenant context can be resolved.  Use this for
    proxy / pass-through routes where the backend service enforces its own
    auth.
    """
    tenant_id = get_tenant_id(request)
    if tenant_id:
        return tenant_id

    # Direct X-Tenant-Id header fallback (mirrors require_tenant priority 1b,
    # including its TRUST_TENANT_HEADER gate — the two must not drift, or a
    # route using optional_tenant would stay forgeable after the other closed)
    if trust_tenant_header():
        x_tenant_id = request.headers.get("x-tenant-id")
        if x_tenant_id:
            request.state.tenant_id = x_tenant_id
            return x_tenant_id

    # Case-insensitive scheme + stripped token, mirroring require_tenant and
    # AuthMiddleware. See the comment there for what the divergence cost.
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        license_data = await _introspect_license(token)
        if license_data and license_data.get("active"):
            # `tenant_id` is the tenant; `subject_id` is the USER (see require_tenant).
            raw_tenant = license_data.get("tenant_id")
            tid = raw_tenant.strip() if isinstance(raw_tenant, str) else ""
            if tid:
                # On-behalf-of, identical rule and identical function to
                # require_tenant.
                #
                # A refused assertion RAISES here even though this function's
                # job is to return None rather than raise. That promise is about
                # the ABSENCE of tenant context — "nobody said who you are, carry
                # on and let the backend decide". A refusal is a different
                # answer: the caller said who it was acting for and may not.
                # Returning None would drop that to "no tenant" and let a
                # pass-through route continue on a default; returning the
                # caller's own tenant would scope the customer's request to the
                # service. Both silently reinterpret a denial as something else.
                effective_tenant, refused = resolve_tenant_assertion(
                    request,
                    subject_id=(license_data.get("subject_id") or None),
                    token_tenant=tid,
                )
                if refused:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            "This credential may not assert a tenant other than the one "
                            "its license names."
                        ),
                    )
                request.state.tenant_id = effective_tenant
                return effective_tenant

    if hasattr(request.state, "user") and request.state.user:
        user: User = request.state.user
        if tid := user.effective_tenant_id:
            return tid

    client_host = request.client.host if request.client else None
    if _is_trusted_network(client_host):
        default_tenant = resolve_default_tenant("the trusted-network bypass in optional_tenant")
        if default_tenant is not None:
            request.state.tenant_id = default_tenant
            return default_tenant

    return None


def get_current_user_with_tenant(request: Request) -> User:
    """Get the current authenticated user with tenant context.

    Works with or without AuthMiddleware:
    1. request.state.user (set by AuthMiddleware when enabled)
    2. X-Tenant-Id / X-User-Id headers (set by gateway proxy or Istio)
    3. Trusted network bypass with DEFAULT_TENANT_ID
    """
    # Priority 1: User already set by AuthMiddleware
    if hasattr(request.state, "user") and request.state.user:
        user: User = request.state.user
        if not user.tenant_id:
            user.tenant_id = user.sub
        return user

    # Priority 2: Construct user from forwarded headers (gateway proxy sets these).
    #
    # Gated on TRUST_TENANT_HEADER. Note this block trusts more than the tenant:
    # `x-user-roles` becomes realm_access["roles"], which feeds User.is_admin(),
    # which `require_same_tenant` honours as "may access ANY tenant". So an
    # unverified `X-User-Roles: admin` is a privilege escalation on top of the
    # tenant forgery, not merely a second instance of it.
    #
    # This function is sync and therefore cannot fall through to license
    # introspection. With the gate off, a header-only caller reaches Priority 4
    # (trusted network, empty by default) and then 401 — so a service that
    # resolves identity ONLY through this dependency must have AuthMiddleware in
    # front of it, or a real license path, before the knob is flipped.
    if trust_tenant_header():
        x_tenant_id = request.headers.get("x-tenant-id")
        x_user_id = request.headers.get("x-user-id")
        if x_tenant_id or x_user_id:
            roles = [r for r in request.headers.get("x-user-roles", "").split(",") if r]
            return User(
                sub=x_user_id or "anonymous",
                preferred_username=request.headers.get("x-user-name", "anonymous"),
                email=request.headers.get("x-user-email"),
                tenant_id=x_tenant_id,
                organization_id=request.headers.get("x-organization-id"),
                realm_access={"roles": roles},
            )

    # Priority 4: Trusted network bypass.
    # NB the User must not be constructed with tenant_id=None as a "safe"
    # degradation: User.model_post_init backfills a blank tenant_id from
    # organization_id/sub, so a None here would quietly become a tenant named
    # after the synthetic subject. Refuse to build the user at all instead.
    client_host = request.client.host if request.client else None
    if _is_trusted_network(client_host):
        default_tenant = resolve_default_tenant(
            "the trusted-network bypass in get_current_user_with_tenant"
        )
        if default_tenant is not None:
            return User(
                sub=default_tenant,
                preferred_username="internal",
                tenant_id=default_tenant,
            )

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


def require_same_tenant(resource_tenant_id: str):
    """Create a dependency that validates the user has access to a specific tenant.

    This is used when accessing a specific resource to ensure the user
    has permission to access that tenant's data.

    Usage:
        @router.get("/containers/{container_id}")
        async def get_container(
            container_id: str,
            user: User = Depends(get_current_user_with_tenant)
        ):
            container = await db.get_container(container_id)
            verify = require_same_tenant(container.tenant_id)
            verify(user)  # Raises if no access
            return container

    Args:
        resource_tenant_id: The tenant_id of the resource being accessed.

    Returns:
        A validator function that checks user access.
    """

    def validator(user: User = Depends(get_current_user_with_tenant)) -> User:
        # Admins can access any tenant
        if user.is_admin():
            return user

        # Regular users can only access their own tenant
        if user.effective_tenant_id != resource_tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: resource belongs to a different tenant",
            )
        return user

    return validator


def check_tenant_access(user: User, resource_tenant_id: str) -> bool:
    """Check if a user has access to a specific tenant's resources.

    This is a utility function for use in business logic where you need
    to check access without raising an exception.

    Args:
        user: The authenticated user.
        resource_tenant_id: The tenant_id of the resource.

    Returns:
        True if user has access, False otherwise.
    """
    # Admins can access any tenant
    if user.is_admin():
        return True

    # Regular users can only access their own tenant
    return user.effective_tenant_id == resource_tenant_id


def create_tenant_context(request: Request):
    """Create a TenantContext from the current request.

    This combines the tenant_id and user information into a TenantContext
    that can be passed to services and background tasks.

    Usage:
        @router.post("/analyze")
        async def analyze(
            request: Request,
            background_tasks: BackgroundTasks,
            tenant_id: str = Depends(require_tenant),
        ):
            ctx = create_tenant_context(request)
            background_tasks.add_task(process_analysis, ctx=ctx, data=data)
            return {"status": "queued"}

    Args:
        request: The FastAPI request object.

    Returns:
        TenantContext with tenant_id and user information.

    Raises:
        HTTPException: If no tenant context is available.
    """
    tenant_id = get_tenant_id(request)
    if not tenant_id and trust_tenant_header():
        # Same unverified claim as require_tenant Priority 1b, same gate.
        # When the gate is off this is normally still fine: require_tenant runs
        # first on these routes and has already written the license-resolved
        # tenant into request.state, which get_tenant_id above returns.
        tenant_id = request.headers.get("x-tenant-id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant context required",
        )
    return {"tenant_id": tenant_id}


def require_tenant_context(request: Request):
    """FastAPI dependency that provides TenantContext.

    This is a convenient dependency for routes that need the full context.

    Usage:
        @router.post("/process")
        async def process(
            ctx: TenantContext = Depends(require_tenant_context),
        ):
            result = await service.process(ctx.tenant_id, data)
            ...

    Args:
        request: The FastAPI request object.

    Returns:
        TenantContext for the current request.
    """
    return create_tenant_context(request)
