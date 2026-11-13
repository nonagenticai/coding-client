"""``coding_client.testing`` is the sanctioned replacement for SKIP_AUTH — test it.

Four repos are about to depend on this module. If it is wrong, their suites go
red in ways that look like their own bug, and the pressure will be to hand-roll
overrides again — which is the exact drift this module exists to prevent.

⚠️ These tests exist because the module shipped with a broken import
(``from .models import User`` — the real path is ``.auth.models``) and NOTHING
caught it: the whole suite was green, `ruff` and `ty` were green, and the wheel
built fine. Nothing imported the module. A clean-venv install of the built wheel
was the first thing to fail. So: import it, call it, and assert its effect on a
real FastAPI app.
"""

from __future__ import annotations

import pytest
from coding_client.auth.models import User
from coding_client.auth.tenant import optional_tenant, require_tenant
from coding_client.testing import (
    DEFAULT_TEST_TENANT,
    override_tenant_auth,
    tenant_auth_override,
)
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/tenant")
    async def read_tenant(tenant_id: str = Depends(require_tenant)):
        return {"tenant_id": tenant_id}

    @app.get("/optional")
    async def read_optional(tenant_id: str | None = Depends(optional_tenant)):
        return {"tenant_id": tenant_id}

    return app


def test_without_the_override_a_credentialless_request_401s():
    """NEGATIVE CONTROL. Without this, every assertion below could pass on an
    app that was never protected to begin with."""
    with TestClient(_app(), raise_server_exceptions=False) as client:
        assert client.get("/tenant").status_code == 401


def test_override_makes_the_protected_route_resolve():
    app = _app()
    override_tenant_auth(app)
    with TestClient(app) as client:
        response = client.get("/tenant")
        assert response.status_code == 200
        assert response.json()["tenant_id"] == DEFAULT_TEST_TENANT


def test_override_covers_optional_tenant_too():
    """The half-configured state is the failure mode this module exists for:
    coding-testing's old conftest overrode three dependencies and not
    require_tenant, and only worked because SKIP_AUTH covered the gap."""
    app = _app()
    override_tenant_auth(app, tenant_id="tenant-a")
    with TestClient(app) as client:
        assert client.get("/optional").json()["tenant_id"] == "tenant-a"
        assert client.get("/tenant").json()["tenant_id"] == "tenant-a"


def test_user_and_tenant_agree_by_default():
    """A route reading both must not see two different tenants."""
    app = _app()
    override_tenant_auth(app, tenant_id="tenant-b")
    from coding_client.auth.tenant import get_current_user_with_tenant

    user = app.dependency_overrides[get_current_user_with_tenant]()
    assert user.tenant_id == "tenant-b"


def test_undo_restores_the_previous_state_exactly():
    app = _app()

    def sentinel() -> str:  # a caller's own override, installed before ours
        return "caller-installed"

    app.dependency_overrides[require_tenant] = sentinel

    undo = override_tenant_auth(app)
    assert app.dependency_overrides[require_tenant] is not sentinel

    undo()
    assert app.dependency_overrides[require_tenant] is sentinel, (
        "undo() must restore a pre-existing override, not drop it — several suites "
        "share a module-level main.app singleton"
    )
    assert optional_tenant not in app.dependency_overrides, (
        "undo() must REMOVE keys it added rather than leaving them behind"
    )


def test_extra_wins_over_the_defaults():
    """coding-ai's require_tenant is a different object and must also set a
    contextvar; coding-analysis returns its own TenantContext. Both go via
    `extra`, so `extra` must be applied last."""
    app = _app()
    override_tenant_auth(app, extra={require_tenant: lambda: "from-extra"})
    with TestClient(app) as client:
        assert client.get("/tenant").json()["tenant_id"] == "from-extra"


def test_custom_user_is_used_verbatim():
    app = _app()
    custom = User(sub="alice", preferred_username="alice", tenant_id="tenant-c")
    override_tenant_auth(app, tenant_id="tenant-c", user=custom)
    from coding_client.auth.dependencies import get_current_user

    assert app.dependency_overrides[get_current_user]() is custom


def test_context_manager_restores_even_when_the_body_raises():
    app = _app()
    with pytest.raises(RuntimeError):
        with tenant_auth_override(app):
            assert require_tenant in app.dependency_overrides
            raise RuntimeError("boom")
    assert require_tenant not in app.dependency_overrides


def test_two_apps_do_not_interfere():
    """Per-app is the whole security argument over an ambient env var."""
    app_a, app_b = _app(), _app()
    override_tenant_auth(app_a, tenant_id="only-a")

    with TestClient(app_a) as client_a:
        assert client_a.get("/tenant").json()["tenant_id"] == "only-a"
    with TestClient(app_b, raise_server_exceptions=False) as client_b:
        assert client_b.get("/tenant").status_code == 401
