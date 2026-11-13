"""Resolution of the fallback tenant handed to credential-less callers.

``DEFAULT_TENANT_ID`` is the tenant granted to a caller that presented **no
credential** and was admitted anyway — the ``TRUSTED_CIDRS`` bypass in
:mod:`._trusted_networks`, and the development/testing API-key path in
:mod:`.middleware`. It is therefore a data-isolation key chosen by
configuration, not by the caller.

Why there is no default value (changed 2026-07-30)
--------------------------------------------------
This module-level constant used to be::

    DEFAULT_TENANT_ID = os.getenv("DEFAULT_TENANT_ID", "n8n-dev")

so a service that never set the variable minted users against the literal
string ``"n8n-dev"``. That literal is not junk and it is not a real tenant_id
either, which is exactly what made it dangerous:

* ``n8n-dev`` **was** a real tenant — as a *text* tenant_id, until the
  2026-04-29 Keycloak migration moved tenant identity to uuid7 and demoted the
  label to a separate ``tenant_name`` attribute.  The canonical id for that
  tenant is now ``0195f48b-d000-7000-8000-000000000001`` (see
  ``the platform's Keycloak realm patch configmap``
  ``TENANT_UUIDS``).
* So the fallback pointed at the *stale label form* of a tenant that really
  exists. Rows written under it land in a silo that no live JWT can ever
  address, and reads under it silently cross out of whatever tenant the
  operator believed the service was serving.

Found live on ``coding-repo-jobs``, which sets no ``DEFAULT_TENANT_ID``:
credential-less callers were reading, and could enqueue, against ``"n8n-dev"``.

There is no safe literal to pick here. The value that would be "consistent"
with coding-analysis / coding-security (``...0001``) is a *different* tenant
from coding-repo-jobs' own ``WORKER_TENANT_ID`` (``...0003``), so any built-in
default is a guess about someone else's data isolation. A missing tenant is
therefore an error: unset means the credential-less paths refuse to mint a
user at all, and — when a bypass is actually armed in production — the process
refuses to boot.
"""

from __future__ import annotations

import logging
import os

from ._trusted_networks import load_trusted_networks

logger = logging.getLogger(__name__)

ENV_VAR = "DEFAULT_TENANT_ID"


def load_default_tenant_id() -> str | None:
    """Read ``DEFAULT_TENANT_ID`` from the environment. **No default value.**

    An empty or whitespace-only value is treated the same as unset, mirroring
    :meth:`coding_client.auth.models.User.model_post_init` — a blank tenant must
    never pin a caller to an empty tenant.
    """
    return os.getenv(ENV_VAR, "").strip() or None


DEFAULT_TENANT_ID: str | None = load_default_tenant_id()


def resolve_default_tenant(purpose: str) -> str | None:
    """Return the configured fallback tenant, or ``None`` — never a literal.

    Callers MUST treat ``None`` as "reject this request". Substituting any
    made-up value here is the bug this module exists to prevent.

    Reads the module attribute at call time (not a captured copy) so tests can
    monkeypatch it, matching :func:`._trusted_networks.is_trusted_network`.
    """
    tenant_id = DEFAULT_TENANT_ID
    if tenant_id is None:
        logger.error(
            "%s is not configured; refusing to invent a tenant for %s. This "
            "caller will be rejected. If this path is meant to be usable, set "
            "%s on the Deployment env block to the tenant it should act as "
            "(see the platform configuration policy).",
            ENV_VAR,
            purpose,
            ENV_VAR,
        )
    return tenant_id


def enforce_default_tenant_configured() -> None:
    """Crash boot when a credential-less bypass is armed with no tenant to grant.

    Follows the repo's fail-loud-in-production convention (see
    :mod:`coding_client.config.base_settings`): a misconfiguration must be
    visible at deploy time, not at 3am on one unlucky request.

    The gate is deliberately narrow — it fires only when *all* of:

    1. ``ENVIRONMENT`` is ``production`` (the default), and
    2. ``TRUSTED_CIDRS`` is non-empty, i.e. an operator has armed the
       credential-less network bypass, and
    3. ``DEFAULT_TENANT_ID`` is unset.

    Condition 2 is what keeps this from being a fleet-wide breaking change:
    ``TRUSTED_CIDRS`` has been empty by default since 1.7.0, and no
    ``coding-client`` consumer sets a non-empty one, so today this raises for
    nobody. It exists so that *re-widening* ``TRUSTED_CIDRS`` without naming the
    tenant fails the rollout instead of silently reviving the literal.

    Raises:
        RuntimeError: never ``ImportError`` — coding-security and coding-testing
            wrap their auth-middleware import in ``except ImportError`` and log
            "running WITHOUT authentication", so an ``ImportError`` here would be
            swallowed into exactly the outcome this check is meant to prevent.
    """
    if os.getenv("ENVIRONMENT", "production") != "production":
        return
    trusted = load_trusted_networks()
    if not trusted:
        return
    if load_default_tenant_id() is not None:
        return
    raise RuntimeError(
        f"TRUSTED_CIDRS is set to {[str(n) for n in trusted]} — requests from "
        f"those networks are admitted with NO credential — but {ENV_VAR} is not "
        f"set, so there is no tenant to grant them. Refusing to start rather "
        f"than serve a made-up tenant. Either set {ENV_VAR} on the Deployment "
        f"env block, or clear TRUSTED_CIDRS to disable the bypass."
    )


enforce_default_tenant_configured()
