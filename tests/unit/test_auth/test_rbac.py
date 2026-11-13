"""Tests for coding_client.auth.rbac and coding_client.auth.rbac_coding."""

import pytest
from coding_client.auth.models import User
from coding_client.auth.rbac import require_access_coding, require_role
from fastapi import HTTPException


class TestRequireRole:
    """Test require_role from rbac module."""

    async def test_returns_user_when_role_present(self, mock_user):
        checker = require_role("coding-access")
        # The rbac.require_role creates an async checker that takes user via Depends
        result = await checker(user=mock_user)
        assert result is mock_user

    async def test_raises_403_when_role_missing(self, mock_user):
        checker = require_role("nonexistent-role")
        with pytest.raises(HTTPException) as exc_info:
            await checker(user=mock_user)
        assert exc_info.value.status_code == 403
        assert "nonexistent-role" in exc_info.value.detail


class TestRequireAccessCoding:
    """Test require_access_coding pre-built dependency."""

    async def test_allows_user_with_coding_access_role(self, mock_user):
        # mock_user has "coding-access" in realm_access.roles
        result = await require_access_coding(user=mock_user)
        assert result is mock_user

    async def test_rejects_user_without_coding_access_role(self):
        user = User(
            sub="u1",
            preferred_username="no-access-user",
            realm_access={"roles": ["user"]},
        )
        with pytest.raises(HTTPException) as exc_info:
            await require_access_coding(user=user)
        assert exc_info.value.status_code == 403


class TestBackwardsCompat:
    """Test backwards compatibility import from rbac_coding."""

    def test_import_from_rbac_coding(self):
        from coding_client.auth.rbac_coding import (
            require_access_coding as rac,
        )
        from coding_client.auth.rbac_coding import (
            require_role as rr,
        )

        # Same objects re-exported
        assert rac is require_access_coding
        assert rr is require_role

    def test_require_access_coding_is_callable(self):
        assert callable(require_access_coding)
