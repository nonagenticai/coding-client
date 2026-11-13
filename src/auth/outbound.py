"""Identity headers for outbound service-to-service calls.

Promoted into the SDK from ``coding-containers/src/clients/_tenant.py``, whose
docstring already made the argument for it: *"this module exists so the 'attach
the tenant' step is one function with one failure mode, rather than N copies of a
header dict that can each be forgotten independently"*. That reasoning applies to
all nine services, and only one of them had the module.

Every client in the fleet talks to a sibling over plain HTTP inside the mesh. The
mesh does **not** inject a tenant identity service-to-service, so each caller has
to send ``X-Tenant-Id`` itself. Several didn't, and were reaching their peer only
because that peer's ``TRUSTED_CIDRS`` covered the pod CIDR — a network position,
not a credential.

The rule that has not changed: **a missing tenant is an error, never a default.**
Substituting ``DEFAULT_TENANT_ID``, ``"anonymous"`` or any other literal makes the
code compile and the call succeed while attributing it to a tenant that does not
own the resource. coding-client removed its ``"n8n-dev"`` fallback for exactly
this reason — that literal was the stale pre-uuid7 label of a *real* tenant, so
substituting it wrote into an unaddressable silo.

What is new: ``service_token``
------------------------------
The caller's own service license, sent as ``Authorization: Bearer <token>``
**without touching ``X-Tenant-Id``**. That separation is the whole point. Putting
the credential in ``X-Tenant-Id`` — as some fleet clients do, overloading the
header — collapses every customer into the calling service's own tenant, because
the callee then resolves the tenant from the token. Keeping them apart is what
lets a caller say "I am the containers service, acting for customer T", which the
callee honours iff the service's subject is allowlisted (see :mod:`._onbehalf`).

``Authorization`` here is the **caller's own** identity. It is never a forwarded
copy of an inbound one: most of these calls are detached (fire-and-forget scans,
``asyncio.create_task`` deep builds, background bulk jobs) and have no inbound
request to borrow a credential from.
"""

from __future__ import annotations

from .tenant import TENANT_ID_HEADER

__all__ = [
    "LICENSE_ID_HEADER",
    "TENANT_ID_HEADER",
    "TenantMissingError",
    "optional_tenant_headers",
    "tenant_headers",
]

#: The customer's license, forwarded so a vouched call is attributable to the
#: license that should be *billed* rather than to the vouching service's own.
LICENSE_ID_HEADER = "X-License-Id"


class TenantMissingError(Exception):
    """An outbound service call had no tenant to attribute itself to.

    Deliberately NOT a subclass of ``ValueError`` / ``RuntimeError`` / ``OSError``
    / ``httpx.HTTPError``, so none of the broad ``except`` clauses that wrap these
    call sites — most of which degrade to a plausible-looking fallback result —
    can silently absorb it. A caller that cannot name its tenant is a bug, and it
    fails loudly.
    """


def _credential_headers(service_token: str | None, license_id: str | None) -> dict[str, str]:
    """The credential half, shared by both builders so they cannot drift."""
    headers: dict[str, str] = {}
    if service_token:
        headers["Authorization"] = f"Bearer {service_token}"
    if license_id:
        headers[LICENSE_ID_HEADER] = license_id
    return headers


def tenant_headers(
    tenant_id: str | None,
    *,
    operation: str,
    service_token: str | None = None,
    license_id: str | None = None,
) -> dict[str, str]:
    """Build the identity headers for an outbound call that is tenant-scoped.

    Args:
        tenant_id: The tenant the call is made on behalf of. Required.
        operation: Human-readable name of the call, for the error message.
        service_token: The caller's own service license. Sent as
            ``Authorization: Bearer``; does not affect ``X-Tenant-Id``.
        license_id: The customer's license id, for attribution.

    Returns:
        ``{"X-Tenant-Id": ...}`` plus any credential headers supplied.

    Raises:
        TenantMissingError: ``tenant_id`` is None or empty.
    """
    if not tenant_id:
        raise TenantMissingError(
            f"Refusing to call {operation} with no tenant. The tenant must be "
            "threaded from the authenticated caller; it is never defaulted, "
            "because attributing a call to a guessed tenant is a cross-tenant "
            "authorisation bug."
        )
    return {TENANT_ID_HEADER: tenant_id, **_credential_headers(service_token, license_id)}


def optional_tenant_headers(
    tenant_id: str | None,
    *,
    service_token: str | None = None,
    license_id: str | None = None,
) -> dict[str, str]:
    """Attach the tenant when there is one, and attach *nothing* when there is not.

    For calls whose authorisation does NOT come from the tenant — coding-github's
    ``/api/internal/github/clone-token`` is guarded by the ``X-Internal-Token``
    shared secret and never reads ``X-Tenant-Id`` at all — refusing the call for a
    missing tenant (:func:`tenant_headers`) would be a regression, because the
    tenant is genuinely optional there and the peer does not want it.

    The rule this preserves is the one that matters: **absent is absent.** A
    ``tenant_id or "anonymous"`` makes every tenantless call claim to come from a
    tenant literally named ``anonymous`` — an identity no registry issues and no
    audit trail can attribute, and one that is indistinguishable downstream from a
    real tenant that happens to be called that.

    Use :func:`tenant_headers` whenever the tenant *scopes the resource* — a
    guessed tenant there is a cross-tenant authorisation bug, not a lost log line.

    Note the credential is still attached when supplied: a call can legitimately
    have no tenant to name while still needing to prove who is making it.
    """
    headers = _credential_headers(service_token, license_id)
    if tenant_id:
        headers[TENANT_ID_HEADER] = tenant_id
    return headers
