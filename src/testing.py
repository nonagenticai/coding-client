"""Test-side helpers for neutralising this SDK's identity dependencies.

This module is the supported replacement for ``SKIP_AUTH=true``, which was
deleted in 1.16.0. The two do the same job for a test suite and differ in the
only way that matters:

    SKIP_AUTH             ambient, global, ENV-triggered, compiled into the
                          production wheel. Anything that could set an
                          environment variable could disable authentication for
                          the whole process, and the branch sat ABOVE every
                          credential path in require_tenant.

    override_tenant_auth  per-app-object, explicit, CALL-triggered. There is no
                          environment variable, no import-time side effect, and
                          no way to reach it except by calling it against a
                          specific FastAPI instance.

That is the entire security delta, and it is enforced rather than asserted:
``tests/unit/test_auth/test_no_auth_bypass.py`` fails if this file ever gains an
``os.getenv``/``os.environ`` read or imports ``pytest``.

WHY THIS IS SHIPPED HERE RATHER THAN WRITTEN PER REPO
-----------------------------------------------------
Because the KEY SET drifts, and it has already drifted. Before 1.16.0,
``coding-testing/tests/integration/conftest.py`` hand-rolled overrides for
``get_current_user``, ``requires_read_permission`` and
``requires_write_permission`` — and NOT ``require_tenant``. That list was
incomplete and nobody knew, because the same conftest also set
``SKIP_AUTH=true`` two lines earlier and covered the gap.

Four repos maintaining that list by hand is four chances to miss the next
dependency this SDK adds. Centralised, adding one is a single edit to
``_TENANT_DEPENDENCIES`` that every consumer picks up at its next pin bump. This
fleet has already been burned twice by forked auth helpers; a third fork, living
in test code where nobody reviews it as security-relevant, is not a good trade
for avoiding one import.

USAGE
-----
    from coding_client.testing import override_tenant_auth

    @pytest.fixture
    def client(app):
        undo = override_tenant_auth(app)
        yield TestClient(app)
        undo()                      # or use the context manager below

    # a service whose own dependency objects differ from the SDK's, or which
    # needs a service-specific return shape:
    undo = override_tenant_auth(
        app,
        tenant_id="tenant-a",
        extra={my_module.create_tenant_context: lambda: MyContext("tenant-a")},
    )

``undo()`` restores the PREVIOUS mapping exactly. It does not call
``.clear()`` — several suites yield a module-level ``main.app`` singleton, and
clearing would silently drop overrides the caller installed itself.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from .auth.dependencies import get_current_user
from .auth.models import User
from .auth.tenant import (
    create_tenant_context,
    get_current_user_with_tenant,
    optional_tenant,
    require_tenant,
    require_tenant_context,
)

__all__ = ["override_tenant_auth", "tenant_auth_override"]

# Every identity dependency this SDK exposes. A route that depends on ANY of
# these must be neutralised, or a suite bypasses auth on some routes and 401s on
# others — which is exactly the half-configured state that made the old
# coding-testing conftest look correct.
#
# ⚠️ Adding a dependency to auth/tenant.py means adding it HERE. That is the
# whole point of this tuple existing.
_TENANT_DEPENDENCIES = (
    require_tenant,
    optional_tenant,
    get_current_user_with_tenant,
    create_tenant_context,
    require_tenant_context,
    get_current_user,
)

DEFAULT_TEST_TENANT = "test-tenant"
DEFAULT_TEST_USER = "test-user"


def override_tenant_auth(
    app: Any,
    *,
    tenant_id: str = DEFAULT_TEST_TENANT,
    user: User | None = None,
    extra: dict[Callable[..., Any], Callable[..., Any]] | None = None,
) -> Callable[[], None]:
    """Neutralise this SDK's identity dependencies on ``app``.

    Args:
        app: the FastAPI application whose ``dependency_overrides`` to install
            into. Per-app, so two apps in one test session cannot interfere.
        tenant_id: what the tenant-returning dependencies resolve to.
        user: what the user-returning dependencies resolve to. Defaults to a
            ``User`` whose ``tenant_id`` matches ``tenant_id`` — they must agree,
            or a route reading both sees two different tenants.
        extra: additional ``{dependency: replacement}`` pairs, merged last so a
            caller can override one of the defaults. Use for a service's own
            forked dependency object (coding-ai's ``require_tenant`` is a
            different object from this SDK's) or for a service-specific return
            shape (coding-analysis's ``create_tenant_context`` returns its own
            ``TenantContext``, not this SDK's dict).

    Returns:
        A zero-argument callable that restores the previous overrides exactly.
    """
    resolved_user = user or User(
        sub=DEFAULT_TEST_USER,
        preferred_username=DEFAULT_TEST_USER,
        tenant_id=tenant_id,
    )

    replacements: dict[Callable[..., Any], Callable[..., Any]] = {
        require_tenant: lambda: tenant_id,
        optional_tenant: lambda: tenant_id,
        get_current_user_with_tenant: lambda: resolved_user,
        create_tenant_context: lambda: {"tenant_id": tenant_id},
        require_tenant_context: lambda: {"tenant_id": tenant_id},
        get_current_user: lambda: resolved_user,
    }
    if extra:
        replacements.update(extra)

    overrides = app.dependency_overrides
    # Snapshot only the keys we touch. Restoring the whole dict would clobber
    # anything installed between our install and undo.
    previous: dict[Callable[..., Any], Any] = {}
    absent: list[Callable[..., Any]] = []
    for dependency, replacement in replacements.items():
        if dependency in overrides:
            previous[dependency] = overrides[dependency]
        else:
            absent.append(dependency)
        overrides[dependency] = replacement

    def undo() -> None:
        for dependency, original in previous.items():
            overrides[dependency] = original
        for dependency in absent:
            overrides.pop(dependency, None)

    return undo


@contextmanager
def tenant_auth_override(
    app: Any,
    *,
    tenant_id: str = DEFAULT_TEST_TENANT,
    user: User | None = None,
    extra: dict[Callable[..., Any], Callable[..., Any]] | None = None,
) -> Iterator[None]:
    """Context-manager form of :func:`override_tenant_auth`.

    Restores on the way out even when the body raises — which a bare
    ``undo()`` after ``yield`` in a fixture does not.
    """
    undo = override_tenant_auth(app, tenant_id=tenant_id, user=user, extra=extra)
    try:
        yield
    finally:
        undo()
