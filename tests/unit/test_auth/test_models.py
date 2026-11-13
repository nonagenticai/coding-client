"""Tests for coding_client.auth.models.User."""

from coding_client.auth.models import User


class TestUserCreation:
    """Test User model construction and defaults."""

    def test_create_with_required_fields_only(self):
        user = User(sub="u1", preferred_username="alice")
        assert user.sub == "u1"
        assert user.preferred_username == "alice"

    def test_default_email_is_none(self):
        user = User(sub="u1", preferred_username="alice")
        assert user.email is None

    def test_default_email_verified_is_false(self):
        user = User(sub="u1", preferred_username="alice")
        assert user.email_verified is False

    def test_default_name_is_none(self):
        user = User(sub="u1", preferred_username="alice")
        assert user.name is None

    def test_default_realm_access_empty_dict(self):
        user = User(sub="u1", preferred_username="alice")
        assert user.realm_access == {}

    def test_default_resource_access_empty_dict(self):
        user = User(sub="u1", preferred_username="alice")
        assert user.resource_access == {}

    def test_default_organization_id_is_none(self):
        user = User(sub="u1", preferred_username="alice")
        assert user.organization_id is None

    def test_explicit_fields(self):
        user = User(
            sub="u1",
            preferred_username="alice",
            email="alice@example.com",
            email_verified=True,
            name="Alice",
            tenant_id="t1",
            organization_id="org1",
        )
        assert user.email == "alice@example.com"
        assert user.email_verified is True
        assert user.name == "Alice"
        assert user.tenant_id == "t1"
        assert user.organization_id == "org1"


class TestModelPostInit:
    """Test post-init tenant_id defaulting logic."""

    def test_tenant_defaults_to_organization_id(self):
        user = User(sub="u1", preferred_username="alice", organization_id="org1")
        assert user.tenant_id == "org1"

    def test_tenant_defaults_to_sub_when_no_org(self):
        user = User(sub="u1", preferred_username="alice")
        assert user.tenant_id == "u1"

    def test_explicit_tenant_not_overwritten(self):
        user = User(sub="u1", preferred_username="alice", tenant_id="t1", organization_id="org1")
        assert user.tenant_id == "t1"

    def test_empty_string_tenant_defaults_to_org(self):
        # The gateway forwards x-tenant-id:"" when a license carries no tenant;
        # an empty string must be treated like None, not pin to a blank tenant.
        user = User(sub="u1", preferred_username="alice", tenant_id="", organization_id="org1")
        assert user.tenant_id == "org1"

    def test_empty_string_tenant_defaults_to_sub_when_no_org(self):
        user = User(sub="u1", preferred_username="alice", tenant_id="")
        assert user.tenant_id == "u1"

    def test_whitespace_tenant_defaults_to_sub(self):
        user = User(sub="u1", preferred_username="alice", tenant_id="   ")
        assert user.tenant_id == "u1"


class TestEffectiveTenantId:
    """Test effective_tenant_id property."""

    def test_returns_tenant_id_first(self):
        user = User(sub="u1", preferred_username="a", tenant_id="t1", organization_id="org1")
        assert user.effective_tenant_id == "t1"

    def test_falls_back_to_organization_id(self):
        user = User(sub="u1", preferred_username="a", organization_id="org1")
        # post_init sets tenant_id to org1, so effective also org1
        assert user.effective_tenant_id == "org1"

    def test_falls_back_to_sub(self):
        user = User(sub="u1", preferred_username="a")
        # post_init sets tenant_id to sub
        assert user.effective_tenant_id == "u1"


class TestHasRealmRole:
    """Test has_realm_role method."""

    def test_role_present(self):
        user = User(sub="u1", preferred_username="a", realm_access={"roles": ["admin", "user"]})
        assert user.has_realm_role("admin") is True

    def test_role_missing(self):
        user = User(sub="u1", preferred_username="a", realm_access={"roles": ["user"]})
        assert user.has_realm_role("admin") is False

    def test_empty_realm_access(self):
        user = User(sub="u1", preferred_username="a")
        assert user.has_realm_role("admin") is False


class TestHasClientRole:
    """Test has_client_role method."""

    def test_client_role_present(self):
        user = User(
            sub="u1",
            preferred_username="a",
            resource_access={"coding-ai": {"roles": ["read", "write"]}},
        )
        assert user.has_client_role("coding-ai", "read") is True

    def test_client_role_missing(self):
        user = User(
            sub="u1",
            preferred_username="a",
            resource_access={"coding-ai": {"roles": ["read"]}},
        )
        assert user.has_client_role("coding-ai", "write") is False

    def test_client_not_present(self):
        user = User(
            sub="u1",
            preferred_username="a",
            resource_access={"other-svc": {"roles": ["read"]}},
        )
        assert user.has_client_role("coding-ai", "read") is False

    def test_empty_resource_access(self):
        user = User(sub="u1", preferred_username="a")
        assert user.has_client_role("coding-ai", "read") is False


class TestGetAllRoles:
    """Test get_all_roles method."""

    def test_combines_realm_and_client_roles(self):
        user = User(
            sub="u1",
            preferred_username="a",
            realm_access={"roles": ["admin"]},
            resource_access={
                "coding-ai": {"roles": ["read"]},
                "svc-b": {"roles": ["write"]},
            },
        )
        roles = user.get_all_roles()
        assert "admin" in roles
        assert "read" in roles
        assert "write" in roles
        assert len(roles) == 3

    def test_empty_roles(self):
        user = User(sub="u1", preferred_username="a")
        assert user.get_all_roles() == []


class TestRolesProperty:
    """Test the .roles bridge property."""

    def test_returns_realm_roles(self):
        user = User(sub="u1", preferred_username="a", realm_access={"roles": ["admin", "user"]})
        assert user.roles == ["admin", "user"]

    def test_empty_when_no_realm_access(self):
        user = User(sub="u1", preferred_username="a")
        assert user.roles == []

    def test_ignores_client_roles(self):
        user = User(
            sub="u1",
            preferred_username="a",
            realm_access={"roles": ["realm-role"]},
            resource_access={"svc": {"roles": ["client-role"]}},
        )
        assert user.roles == ["realm-role"]


class TestIsAdmin:
    """Test is_admin method."""

    def test_admin_role(self):
        user = User(sub="u1", preferred_username="a", realm_access={"roles": ["admin"]})
        assert user.is_admin() is True

    def test_platform_admin_role(self):
        user = User(sub="u1", preferred_username="a", realm_access={"roles": ["platform-admin"]})
        assert user.is_admin() is True

    def test_non_admin(self):
        user = User(sub="u1", preferred_username="a", realm_access={"roles": ["user"]})
        assert user.is_admin() is False

    def test_no_roles(self):
        user = User(sub="u1", preferred_username="a")
        assert user.is_admin() is False


class TestSerialization:
    """Test model serialization."""

    def test_model_dump_includes_all_fields(self):
        user = User(
            sub="u1",
            preferred_username="alice",
            email="alice@example.com",
            email_verified=True,
            name="Alice",
            tenant_id="t1",
            organization_id="org1",
            realm_access={"roles": ["admin"]},
            resource_access={"svc": {"roles": ["r"]}},
        )
        dumped = user.model_dump()
        assert dumped["sub"] == "u1"
        assert dumped["preferred_username"] == "alice"
        assert dumped["email"] == "alice@example.com"
        assert dumped["email_verified"] is True
        assert dumped["name"] == "Alice"
        assert dumped["tenant_id"] == "t1"
        assert dumped["organization_id"] == "org1"
        assert dumped["realm_access"] == {"roles": ["admin"]}
        assert dumped["resource_access"] == {"svc": {"roles": ["r"]}}
