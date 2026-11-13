"""KAG-standard OpenAPI schema customization.

Adds Bearer token security scheme and X-Tenant-ID header parameter
to the OpenAPI specification.
"""

from __future__ import annotations

import os
from collections.abc import Set

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def configure_openapi(
    app: FastAPI,
    *,
    protected_prefixes: Set[str] | None = None,
    public_endpoints: Set[str] | None = None,
    default_tenant_id: str | None = None,
) -> None:
    """Replace app.openapi with a KAG-standard schema generator.

    Args:
        app: FastAPI application instance.
        protected_prefixes: Route prefixes requiring Bearer auth (e.g. {"/api/graphs"}).
        public_endpoints: Exact paths that are always public (e.g. {"/", "/health"}).
        default_tenant_id: Default tenant ID shown in docs. When omitted it is
            read from the ``DEFAULT_TENANT_ID`` env var; if that is unset too,
            the header is documented as **required** with no default, because
            there is none. It must not advertise a literal the service was never
            configured with — the docs previously showed ``n8n-dev``, the stale
            pre-uuid7 label form of a real tenant (see
            ``coding_client.auth._default_tenant``).
    """
    if protected_prefixes is None:
        protected_prefixes = set()
    if public_endpoints is None:
        public_endpoints = {
            "/",
            "/health",
            "/health/ready",
            "/health/live",
            "/docs",
            "/redoc",
            "/openapi.json",
        }
    if default_tenant_id is None:
        default_tenant_id = os.getenv("DEFAULT_TENANT_ID", "").strip() or None

    app.openapi_schema = None  # Reset to force regeneration

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        components = openapi_schema.setdefault("components", {})

        # Bearer token security scheme
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes["BearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter your Bearer JWT token",
        }

        # Reusable tenant header parameter
        parameters = components.setdefault("parameters", {})
        tenant_header: dict = {
            "name": "X-Tenant-ID",
            "in": "header",
            "required": default_tenant_id is None,
            "description": (
                "Tenant identifier (defaults to configured DEFAULT_TENANT_ID)."
                if default_tenant_id is not None
                else "Tenant identifier. Required: this service has no "
                "DEFAULT_TENANT_ID configured, so there is no fallback tenant."
            ),
            "schema": {"type": "string"},
        }
        if default_tenant_id is not None:
            tenant_header["schema"]["default"] = default_tenant_id
            tenant_header["example"] = default_tenant_id
        parameters.setdefault("TenantIdHeader", tenant_header)

        # Apply security only to protected prefixes
        for path, path_item in openapi_schema.get("paths", {}).items():
            normalized_path = path.rstrip("/") or "/"
            requires_auth = (
                any(normalized_path.startswith(prefix) for prefix in protected_prefixes)
                and normalized_path not in public_endpoints
            )

            for operation in path_item.values():
                if not isinstance(operation, dict):
                    continue

                if requires_auth:
                    operation.setdefault("security", [{"BearerAuth": []}])
                else:
                    operation.pop("security", None)

                # Add tenant header parameter to all operations
                op_params = operation.setdefault("parameters", [])
                has_tenant = any(
                    p.get("name", "").lower() == "x-tenant-id" and p.get("in") == "header"
                    for p in op_params
                )
                if not has_tenant:
                    op_params.append({"$ref": "#/components/parameters/TenantIdHeader"})

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    setattr(app, "openapi", custom_openapi)
