"""Tests for coding_client.api.openapi_config.

Focused on the ``X-Tenant-ID`` header parameter, which used to advertise the
literal ``"n8n-dev"`` as its documented default and example whenever
``DEFAULT_TENANT_ID`` was unset. That is the doc-facing half of the same
fallback-literal defect fixed in ``coding_client.auth._default_tenant``: the
published OpenAPI schema of every unconfigured coding-* service told callers to
send a tenant that nobody owns.
"""

from coding_client.api.openapi_config import configure_openapi
from fastapi import FastAPI


def _tenant_header(app: FastAPI) -> dict:
    schema = app.openapi()
    return schema["components"]["parameters"]["TenantIdHeader"]


class TestTenantIdHeaderParameter:
    def test_no_literal_default_when_unconfigured(self, monkeypatch):
        """FAILS against 1.7.1, which documented default/example == "n8n-dev"."""
        monkeypatch.delenv("DEFAULT_TENANT_ID", raising=False)
        app = FastAPI()
        configure_openapi(app, protected_prefixes={"/api"})

        param = _tenant_header(app)
        assert "default" not in param["schema"]
        assert "example" not in param
        assert "n8n-dev" not in str(param)
        # With no fallback tenant the header is the only way to name one.
        assert param["required"] is True

    def test_blank_env_is_treated_as_unconfigured(self, monkeypatch):
        monkeypatch.setenv("DEFAULT_TENANT_ID", "   ")
        app = FastAPI()
        configure_openapi(app, protected_prefixes={"/api"})

        param = _tenant_header(app)
        assert "default" not in param["schema"]
        assert param["required"] is True

    def test_configured_tenant_is_documented(self, monkeypatch):
        """False-positive control: the default is still published when it exists."""
        monkeypatch.setenv("DEFAULT_TENANT_ID", "0195f48b-d000-7000-8000-000000000001")
        app = FastAPI()
        configure_openapi(app, protected_prefixes={"/api"})

        param = _tenant_header(app)
        assert param["schema"]["default"] == "0195f48b-d000-7000-8000-000000000001"
        assert param["example"] == "0195f48b-d000-7000-8000-000000000001"
        assert param["required"] is False

    def test_explicit_argument_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("DEFAULT_TENANT_ID", "from-env")
        app = FastAPI()
        configure_openapi(app, protected_prefixes={"/api"}, default_tenant_id="explicit")

        assert _tenant_header(app)["schema"]["default"] == "explicit"
