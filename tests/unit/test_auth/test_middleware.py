"""Tests for coding_client.auth.middleware.AuthMiddleware."""

import os
from unittest.mock import patch

from coding_client.auth import _default_tenant as dt_mod
from coding_client.auth.middleware import AuthMiddleware
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient


def _user_info_endpoint(request: Request) -> JSONResponse:
    """Test endpoint that returns user info from request.state."""
    if hasattr(request.state, "user") and request.state.user:
        user = request.state.user
        return JSONResponse(
            {
                "sub": user.sub,
                "username": user.preferred_username,
                "tenant_id": user.tenant_id,
                "roles": user.realm_access.get("roles", []),
            }
        )
    return JSONResponse({"error": "no user"}, status_code=500)


def _build_app() -> Starlette:
    """Build a minimal Starlette app with AuthMiddleware."""
    app = Starlette(
        routes=[
            Route("/health", lambda r: JSONResponse({"ok": True})),
            Route("/ready", lambda r: JSONResponse({"ok": True})),
            Route("/metrics", lambda r: JSONResponse({"ok": True})),
            Route("/docs", lambda r: JSONResponse({"ok": True})),
            Route("/openapi.json", lambda r: JSONResponse({"ok": True})),
            Route("/api/test", _user_info_endpoint),
        ],
    )
    app.add_middleware(AuthMiddleware)
    return app


class TestPublicPaths:
    """AuthMiddleware must skip auth for public paths."""

    def test_health_skips_auth(self):
        client = TestClient(_build_app())
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_ready_skips_auth(self):
        client = TestClient(_build_app())
        resp = client.get("/ready")
        assert resp.status_code == 200

    def test_metrics_skips_auth(self):
        client = TestClient(_build_app())
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_docs_skips_auth(self):
        client = TestClient(_build_app())
        resp = client.get("/docs")
        assert resp.status_code == 200

    def test_openapi_json_skips_auth(self):
        client = TestClient(_build_app())
        resp = client.get("/openapi.json")
        assert resp.status_code == 200


class TestDevModeApiKey:
    """Dev mode with DEV_API_KEY creates a dev user.

    These tests now configure DEFAULT_TENANT_ID explicitly. They used to pass
    without it because the library substituted the literal ``"n8n-dev"``, and
    none of them asserted on ``tenant_id`` — so the invented tenant was never
    visible in the expectations. Configuring it (and asserting it) is the actual
    contract: a dev API key says *who*, never *which tenant*.
    """

    CONFIGURED_TENANT = "0195f48b-d000-7000-8000-000000000001"

    def test_valid_dev_api_key_creates_dev_user(self):
        env = {"ENVIRONMENT": "development", "DEV_API_KEY": "secret-key"}
        with (
            patch.dict(os.environ, env, clear=False),
            patch.object(dt_mod, "DEFAULT_TENANT_ID", self.CONFIGURED_TENANT),
        ):
            client = TestClient(_build_app())
            resp = client.get("/api/test", headers={"Authorization": "Bearer secret-key"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["sub"] == "dev-user"
        assert data["username"] == "dev-user"
        assert data["tenant_id"] == self.CONFIGURED_TENANT
        assert "admin" in data["roles"]

    def test_valid_test_api_key_creates_dev_user(self):
        env = {"ENVIRONMENT": "testing", "TEST_API_KEY": "test-key"}
        with (
            patch.dict(os.environ, env, clear=False),
            patch.object(dt_mod, "DEFAULT_TENANT_ID", self.CONFIGURED_TENANT),
        ):
            client = TestClient(_build_app())
            resp = client.get("/api/test", headers={"Authorization": "Bearer test-key"})
        assert resp.status_code == 200
        assert resp.json()["sub"] == "dev-user"
        assert resp.json()["tenant_id"] == self.CONFIGURED_TENANT

    def test_invalid_api_key_falls_through_to_trusted(self):
        """Wrong API key in dev mode falls through; trusted network creates internal user."""
        env = {"ENVIRONMENT": "development", "DEV_API_KEY": "correct-key"}
        with (
            patch.dict(os.environ, env, clear=False),
            patch.object(dt_mod, "DEFAULT_TENANT_ID", self.CONFIGURED_TENANT),
        ):
            # TestClient reports client.host="testclient", so patch trusted check
            with patch("coding_client.auth.middleware._is_trusted_network", return_value=True):
                client = TestClient(_build_app())
                resp = client.get("/api/test", headers={"Authorization": "Bearer wrong-key"})
        assert resp.status_code == 200
        data = resp.json()
        # Should NOT be dev-user since key was wrong -- falls to trusted network user
        assert data["sub"] != "dev-user"
        assert data["username"] == "internal"
        assert data["tenant_id"] == self.CONFIGURED_TENANT

    def test_invalid_api_key_untrusted_returns_401(self):
        """Wrong API key in dev mode + untrusted network returns 401."""
        env = {"ENVIRONMENT": "development", "DEV_API_KEY": "correct-key"}
        with patch.dict(os.environ, env, clear=False):
            with patch("coding_client.auth.middleware._is_trusted_network", return_value=False):
                client = TestClient(_build_app(), raise_server_exceptions=False)
                resp = client.get("/api/test", headers={"Authorization": "Bearer wrong-key"})
        assert resp.status_code == 401


class TestIstioHeaders:
    """Test user creation from Istio-forwarded headers."""

    def test_creates_user_from_istio_headers(self):
        env = {"ENVIRONMENT": "production"}
        with patch.dict(os.environ, env, clear=False):
            client = TestClient(_build_app())
            resp = client.get(
                "/api/test",
                headers={
                    "x-user-id": "istio-user-42",
                    "x-tenant-id": "tenant-99",
                    "x-user-name": "istio-alice",
                    "x-user-roles": "admin,user",
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sub"] == "istio-user-42"
        assert data["tenant_id"] == "tenant-99"
        assert data["username"] == "istio-alice"
        assert "admin" in data["roles"]
        assert "user" in data["roles"]

    def test_anonymous_when_only_tenant_header(self):
        env = {"ENVIRONMENT": "production"}
        with patch.dict(os.environ, env, clear=False):
            client = TestClient(_build_app())
            resp = client.get("/api/test", headers={"x-tenant-id": "tenant-99"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["sub"] == "anonymous"
        assert data["tenant_id"] == "tenant-99"

    def test_empty_roles_header(self):
        env = {"ENVIRONMENT": "production"}
        with patch.dict(os.environ, env, clear=False):
            client = TestClient(_build_app())
            resp = client.get(
                "/api/test",
                headers={"x-user-id": "u1", "x-user-roles": ""},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["roles"] == []


class TestTrustedNetwork:
    """Trusted network (loopback) gets internal user."""

    def test_trusted_network_creates_internal_user(self):
        """Trusted network (patched) creates internal user with the CONFIGURED tenant."""
        env = {"ENVIRONMENT": "production"}
        configured = "0195f48b-d000-7000-8000-000000000001"
        with patch.dict(os.environ, env, clear=False):
            # TestClient reports client.host="testclient", not a real IP
            with (
                patch("coding_client.auth.middleware._is_trusted_network", return_value=True),
                patch.object(dt_mod, "DEFAULT_TENANT_ID", configured),
            ):
                client = TestClient(_build_app())
                resp = client.get("/api/test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "internal"
        assert data["tenant_id"] == configured

    def test_trusted_network_401s_when_no_tenant_configured(self):
        """Negative control for the 2026-07-30 fix.

        A service that sets no DEFAULT_TENANT_ID must NOT end up serving
        ``"n8n-dev"``. Against 1.7.1 this returns 200 with
        ``tenant_id == "n8n-dev"``; the assertion is on the response the caller
        actually gets, not on any helper having been consulted.

        Live blast radius: coding-github and coding-repo-jobs are the two
        coding-client consumers with no DEFAULT_TENANT_ID. Both also set
        ``TRUSTED_CIDRS: ""``, so ``_is_trusted_network`` is False for them in
        production and this branch is unreachable — which is why removing the
        literal outright is safe rather than needing a compatibility knob.
        """
        env = {"ENVIRONMENT": "production"}
        with patch.dict(os.environ, env, clear=False):
            with (
                patch("coding_client.auth.middleware._is_trusted_network", return_value=True),
                patch.object(dt_mod, "DEFAULT_TENANT_ID", None),
            ):
                client = TestClient(_build_app(), raise_server_exceptions=False)
                resp = client.get("/api/test")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Authentication required"
        assert "n8n-dev" not in resp.text

    def test_dev_api_key_does_not_mint_a_tenant_when_unconfigured(self):
        """The dev API key proves identity, never which tenant. No tenant => no auth."""
        env = {
            "ENVIRONMENT": "development",
            "DEV_API_KEY": "dev-secret",  # pragma: allowlist secret
        }
        with patch.dict(os.environ, env, clear=False):
            with (
                patch("coding_client.auth.middleware._is_trusted_network", return_value=False),
                patch.object(dt_mod, "DEFAULT_TENANT_ID", None),
            ):
                client = TestClient(_build_app(), raise_server_exceptions=False)
                resp = client.get("/api/test", headers={"authorization": "Bearer dev-secret"})
        assert resp.status_code == 401
        assert "n8n-dev" not in resp.text

    def test_dev_api_key_still_works_when_tenant_is_configured(self):
        """False-positive control: the dev API-key path is not simply dead."""
        env = {
            "ENVIRONMENT": "development",
            "DEV_API_KEY": "dev-secret",  # pragma: allowlist secret
        }
        configured = "0195f48b-d000-7000-8000-000000000003"
        with patch.dict(os.environ, env, clear=False):
            with (
                patch("coding_client.auth.middleware._is_trusted_network", return_value=False),
                patch.object(dt_mod, "DEFAULT_TENANT_ID", configured),
            ):
                client = TestClient(_build_app())
                resp = client.get("/api/test", headers={"authorization": "Bearer dev-secret"})
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == configured


class TestUntrustedNetwork:
    """Untrusted network without headers returns 401."""

    def test_untrusted_returns_401(self):
        env = {"ENVIRONMENT": "production"}
        with patch.dict(os.environ, env, clear=False):
            # Patch _is_trusted_network to return False for this test
            with patch("coding_client.auth.middleware._is_trusted_network", return_value=False):
                client = TestClient(_build_app(), raise_server_exceptions=False)
                resp = client.get("/api/test")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Authentication required"

    def test_untrusted_returns_json_content_type(self):
        env = {"ENVIRONMENT": "production"}
        with patch.dict(os.environ, env, clear=False):
            with patch("coding_client.auth.middleware._is_trusted_network", return_value=False):
                client = TestClient(_build_app(), raise_server_exceptions=False)
                resp = client.get("/api/test")
        assert "application/json" in resp.headers.get("content-type", "")
