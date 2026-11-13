"""Tests for coding_client.auth.dependencies."""

from unittest.mock import MagicMock

import pytest
from coding_client.auth.dependencies import (
    get_current_user,
    require_any_role,
    require_role,
)
from fastapi import HTTPException


class TestGetCurrentUser:
    """Test get_current_user dependency."""

    def test_returns_user_from_state(self, mock_request, mock_user):
        result = get_current_user(mock_request)
        assert result is mock_user

    def test_raises_401_when_no_state_user(self):
        request = MagicMock()
        request.state = MagicMock(spec=[])  # no 'user' attribute
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(request)
        assert exc_info.value.status_code == 401
        assert "Authentication required" in exc_info.value.detail

    def test_raises_401_when_state_missing(self):
        request = MagicMock(spec=[])  # no 'state' attribute either
        # hasattr(request.state, "user") will fail because state doesn't exist
        # but MagicMock() will create it on access. Use spec=[] to prevent that.
        # Actually we need state to exist but without user.
        request = MagicMock()
        del request.state.user  # remove the auto-generated attribute
        # MagicMock deletes it but hasattr may still return True in some cases
        # Use a real object to be safe:
        request.state = type("State", (), {})()
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(request)
        assert exc_info.value.status_code == 401


class TestRequireRole:
    """Test require_role dependency factory."""

    def test_returns_user_when_role_present(self, mock_request, mock_user):
        checker = require_role("coding-access")
        result = checker(mock_request)
        assert result is mock_user

    def test_raises_403_when_role_missing(self, mock_request):
        checker = require_role("superadmin")
        with pytest.raises(HTTPException) as exc_info:
            checker(mock_request)
        assert exc_info.value.status_code == 403
        assert "superadmin" in exc_info.value.detail

    def test_raises_401_when_no_user(self):
        request = MagicMock()
        request.state = type("State", (), {})()
        checker = require_role("admin")
        with pytest.raises(HTTPException) as exc_info:
            checker(request)
        assert exc_info.value.status_code == 401


class TestRequireAnyRole:
    """Test require_any_role dependency factory."""

    def test_returns_user_when_first_role_present(self, mock_request, mock_user):
        checker = require_any_role("coding-access", "admin")
        result = checker(mock_request)
        assert result is mock_user

    def test_returns_user_when_second_role_present(self, mock_request, mock_user):
        # mock_user has "coding-access" and "user" roles
        checker = require_any_role("admin", "user")
        result = checker(mock_request)
        assert result is mock_user

    def test_raises_403_when_no_role_present(self, mock_request):
        checker = require_any_role("superadmin", "root")
        with pytest.raises(HTTPException) as exc_info:
            checker(mock_request)
        assert exc_info.value.status_code == 403
        assert "superadmin" in exc_info.value.detail
        assert "root" in exc_info.value.detail

    def test_raises_401_when_no_user(self):
        request = MagicMock()
        request.state = type("State", (), {})()
        checker = require_any_role("admin", "editor")
        with pytest.raises(HTTPException) as exc_info:
            checker(request)
        assert exc_info.value.status_code == 401
