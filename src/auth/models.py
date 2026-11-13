"""User models for header-based auth with tenant isolation support."""

from pydantic import BaseModel, Field


class User(BaseModel):
    """User model with header-based auth and tenant isolation.

    Tenant isolation is provided via the tenant_id field, which can be:
    1. Set from X-User-Id and X-Tenant-Id headers (set by Istio gateway)
    2. Defaults to user's sub (user ID) for single-user tenants
    """

    sub: str = Field(..., description="User ID")
    preferred_username: str = Field(..., description="Username")
    email: str | None = None
    email_verified: bool = False
    name: str | None = None

    # Roles from X-User-Roles header
    realm_access: dict = Field(default_factory=dict)
    resource_access: dict = Field(default_factory=dict)

    # Tenant isolation - from X-Tenant-Id header
    tenant_id: str | None = Field(default=None, description="Tenant identifier for data isolation")

    # Optional organization fields
    organization_id: str | None = Field(default=None, description="Organization ID")

    def model_post_init(self, __context) -> None:
        """Ensure tenant_id is set after model initialization.

        An empty or whitespace-only ``tenant_id`` is treated the same as
        ``None``. Upstream services forward ``x-tenant-id: ""`` when a license
        token carries no tenant (e.g. the gateway's ``user.tenant_id or ""``),
        and a blank value must NOT pin the user to an empty tenant — that
        silently breaks data isolation. Fall back to ``organization_id`` then
        ``sub`` instead.
        """
        if not (self.tenant_id or "").strip():
            # Priority: organization_id > sub (user ID as fallback tenant)
            self.tenant_id = self.organization_id or self.sub

    @property
    def effective_tenant_id(self) -> str:
        """Get the effective tenant ID for data filtering.

        Returns:
            The tenant_id, organization_id, or sub as fallback.
        """
        return self.tenant_id or self.organization_id or self.sub

    @property
    def roles(self) -> list[str]:
        """Realm roles as a flat list.

        Bridge accessor so callers can read ``user.roles`` directly instead of
        reaching into ``realm_access["roles"]``. Mirrors the realm-role half of
        :meth:`get_all_roles`.
        """
        return self.realm_access.get("roles", [])

    def has_realm_role(self, role: str) -> bool:
        """Check if user has realm role."""
        roles = self.realm_access.get("roles", [])
        return role in roles

    def has_client_role(self, client_id: str, role: str) -> bool:
        """Check if user has client role."""
        client_roles = self.resource_access.get(client_id, {}).get("roles", [])
        return role in client_roles

    def get_all_roles(self) -> list[str]:
        """Get all roles (realm + client)."""
        realm_roles = self.realm_access.get("roles", [])
        client_roles = []
        for client_data in self.resource_access.values():
            client_roles.extend(client_data.get("roles", []))
        return realm_roles + client_roles

    def is_admin(self) -> bool:
        """Check if user has admin privileges (can access all tenants)."""
        return self.has_realm_role("admin") or self.has_realm_role("platform-admin")
