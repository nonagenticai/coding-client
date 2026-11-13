"""Trusted-network evaluation for the auth layer.

``TRUSTED_CIDRS`` lets an operator nominate source networks whose requests are
accepted **without any credential** and granted ``DEFAULT_TENANT_ID``. It is an
authentication *bypass*, so its default is empty: a caller is trusted only when
someone deliberately says so.

Arming it takes two decisions, not one: *which* networks (here) and *which
tenant* they then act as (``DEFAULT_TENANT_ID``, see :mod:`._default_tenant`,
which has no default either and refuses to boot if this list is non-empty while
it is unset).

Why the default is empty (changed 2026-07-29)
---------------------------------------------
The previous default was
``127.0.0.1/32,::1/128,192.168.0.0/16,172.16.0.0/12,10.0.0.0/8``. On this fleet
every pod carries an address in the k3s pod CIDR ``10.42.0.0/16``, which is a
subset of ``10.0.0.0/8`` — so **every pod in the cluster** satisfied the bypass
and was handed ``DEFAULT_TENANT_ID`` instead of a 401. That was demonstrated
live: an unrelated pod in the ``artifacts`` namespace, with no Authorization
header, no X-Tenant-Id and no license token, read
``GET /api/containers/`` from coding-containers and got HTTP 200 with data.

"The caller's IP looks local" is not authentication in a cluster where every
workload is local. Legitimate in-mesh callers do not need this: coding-gateway
strips client-supplied identity headers and re-injects ``x-tenant-id`` from the
value it resolved itself (see ``coding-gateway`` ``routers/proxy.py``), so
backends receive tenant context as a header from the gateway, and the mesh
AuthorizationPolicy is what restricts who may reach the port at all.

This module exists so the parsing lives in exactly one place. It previously
existed as byte-identical copies in ``middleware.py`` and ``tenant.py``; a fix
applied to one would silently have left the other permissive.
"""

from __future__ import annotations

import ipaddress
import logging
import os

logger = logging.getLogger(__name__)

_Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def _parse_cidrs(raw: str) -> list[_Network]:
    """Parse a comma-separated CIDR list, skipping (and logging) bad entries.

    A malformed entry must not take the whole list down to empty, because an
    empty list is *more* restrictive and would turn a typo into an outage that
    looks like an auth bug.
    """
    networks: list[_Network] = []
    for chunk in raw.split(","):
        cidr = chunk.strip()
        if not cidr:
            continue
        try:
            networks.append(ipaddress.ip_network(cidr, strict=False))
        except ValueError:
            logger.error("TRUSTED_CIDRS: ignoring unparseable entry %r", cidr)
    return networks


def load_trusted_networks() -> list[_Network]:
    """Read ``TRUSTED_CIDRS`` from the environment. Empty by default."""
    return _parse_cidrs(os.getenv("TRUSTED_CIDRS", ""))


TRUSTED_NETWORKS: list[_Network] = load_trusted_networks()

if TRUSTED_NETWORKS:
    logger.warning(
        "TRUSTED_CIDRS is set to %s — requests from these networks are accepted "
        "with NO credential and granted DEFAULT_TENANT_ID. This is an "
        "authentication bypass; confirm it is intended.",
        [str(n) for n in TRUSTED_NETWORKS],
    )


def is_trusted_network(host: str | None) -> bool:
    """True if *host* is a literal IP inside a configured trusted network.

    Reads :data:`TRUSTED_NETWORKS` at call time (not a captured copy) so tests
    can monkeypatch the module attribute.
    """
    if not host:
        return False
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(addr in net for net in TRUSTED_NETWORKS)
