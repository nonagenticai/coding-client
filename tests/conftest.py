"""Shared test fixtures."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from coding_client.auth.models import User


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_user():
    """Standard authenticated user with tenant."""
    return User(
        sub="user-123",
        preferred_username="testuser",
        email="test@example.com",
        email_verified=True,
        name="Test User",
        tenant_id="tenant-abc",
        organization_id="org-xyz",
        realm_access={"roles": ["coding-access", "user"]},
        resource_access={"coding-ai": {"roles": ["read", "write"]}},
    )


@pytest.fixture
def admin_user():
    """Admin user with admin realm role."""
    return User(
        sub="admin-001",
        preferred_username="admin",
        email="admin@example.com",
        email_verified=True,
        name="Admin User",
        tenant_id="tenant-abc",
        organization_id="org-xyz",
        realm_access={"roles": ["admin", "coding-access", "user"]},
        resource_access={},
    )


@pytest.fixture
def mock_request(mock_user):
    """Mock FastAPI Request with state/headers/client."""
    request = MagicMock()
    request.state = MagicMock()
    request.state.user = mock_user
    request.state.tenant_id = mock_user.effective_tenant_id
    request.headers = {
        "x-user-id": mock_user.sub,
        "x-tenant-id": mock_user.tenant_id,
        "x-user-name": mock_user.preferred_username,
        "x-user-roles": ",".join(mock_user.realm_access.get("roles", [])),
    }
    request.url = MagicMock()
    request.url.path = "/api/test"
    request.method = "GET"
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    return request
