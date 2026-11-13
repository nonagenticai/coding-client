"""Tests for coding_client.auth.tenant module."""

import hashlib
import ipaddress
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from coding_client.auth import _default_tenant as dt_mod
from coding_client.auth import _trusted_networks as tn_mod
from coding_client.auth._default_tenant import (
    enforce_default_tenant_configured,
    load_default_tenant_id,
    resolve_default_tenant,
)
from coding_client.auth._trusted_networks import load_trusted_networks
from coding_client.auth.models import User
from coding_client.auth.tenant import (
    _introspect_license,
    _is_trusted_network,
    _license_cache,
    _negative_license_cache,
    check_tenant_access,
    clear_license_caches,
    create_tenant_context,
    get_current_user_with_tenant,
    get_tenant_id,
    optional_tenant,
    require_same_tenant,
    require_tenant,
)
from fastapi import HTTPException


@pytest.fixture(autouse=True)
def _set_license_introspect_url(monkeypatch):
    """Provide a non-empty LICENSE_INTROSPECT_URL for every test in this module.

    The runtime no longer carries a hardcoded fallback (config-externalization
    policy: the platform configuration policy), so tests
    that exercise ``_introspect_license`` need the env var set or the call
    short-circuits to ``None``.
    """
    monkeypatch.setenv("LICENSE_INTROSPECT_URL", "http://test-licenses/license/introspect")
    # Both introspection caches, before AND after: since refusals are cached
    # too, a token refused in one test would suppress the outbound call another
    # test is counting. The per-test `_license_cache.clear()` calls below predate
    # the negative cache and are no longer sufficient on their own.
    clear_license_caches()
    yield
    clear_license_caches()


# ---------------------------------------------------------------------------
# get_tenant_id
# ---------------------------------------------------------------------------
class TestGetTenantId:
    """Test get_tenant_id dependency."""

    def test_returns_tenant_from_state(self):
        request = MagicMock()
        request.state.tenant_id = "t-100"
        assert get_tenant_id(request) == "t-100"

    def test_returns_none_when_not_set(self):
        request = MagicMock()
        request.state = type("State", (), {})()  # no tenant_id attribute
        assert get_tenant_id(request) is None


# ---------------------------------------------------------------------------
# require_tenant
# ---------------------------------------------------------------------------
class TestRequireTenant:
    """Test require_tenant dependency with multiple priority fallbacks."""

    @pytest.mark.parametrize("value", ["true", "True", "TRUE", "1", "yes"])
    async def test_skip_auth_no_longer_bypasses_anything(self, monkeypatch, value):
        """SKIP_AUTH was deleted in 1.16.0 — setting it must change NOTHING.

        These two tests used to assert the opposite: that SKIP_AUTH=true made
        require_tenant hand back "test-tenant" before looking at a credential.
        They are inverted rather than deleted, because deleting them would leave
        the removal itself untested — nothing would notice the hatch coming back.

        A credential-less request must 401 with the variable set exactly as it
        does without it. The case-insensitivity the old test pinned is now
        irrelevant, so every casing is swept, plus the two other spellings a
        re-implementation would plausibly reach for.
        """
        monkeypatch.setenv("SKIP_AUTH", value)
        request = MagicMock()
        request.state = type("State", (), {})()  # no tenant_id, no user
        request.headers = {}

        with pytest.raises(HTTPException) as exc:
            await require_tenant(request)
        assert exc.value.status_code == 401

    async def test_returns_from_state_tenant_id(self, monkeypatch):
        monkeypatch.delenv("SKIP_AUTH", raising=False)
        request = MagicMock()
        request.state.tenant_id = "from-state"
        request.headers = {}
        result = await require_tenant(request)
        assert result == "from-state"

    async def test_license_introspection_fallback(self, monkeypatch):
        monkeypatch.delenv("SKIP_AUTH", raising=False)
        _license_cache.clear()

        request = MagicMock()
        request.state = type("State", (), {})()  # no tenant_id
        request.headers = {"Authorization": "Bearer license-token-xyz"}
        request.client = MagicMock()
        request.client.host = "8.8.8.8"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"active": True, "tenant_id": "lic-tenant"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("coding_client.auth.tenant.httpx.AsyncClient", return_value=mock_client):
            result = await require_tenant(request)
        assert result == "lic-tenant"

    async def test_bearer_resolves_tenant_id_not_subject_id(self, monkeypatch):
        """Regression: the tenant is `tenant_id` (workspace), not `subject_id`
        (the user). When the introspection returns both, scope on tenant_id."""
        monkeypatch.delenv("SKIP_AUTH", raising=False)
        _license_cache.clear()

        request = MagicMock()
        request.state = type("State", (), {})()
        request.headers = {"Authorization": "Bearer license-token-both"}
        request.client = MagicMock()
        request.client.host = "8.8.8.8"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "active": True,
            "tenant_id": "the-tenant",
            "subject_id": "the-user",
        }
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("coding_client.auth.tenant.httpx.AsyncClient", return_value=mock_client):
            result = await require_tenant(request)
        assert result == "the-tenant"
        assert result != "the-user"

    async def test_user_state_fallback(self, monkeypatch, mock_user):
        monkeypatch.delenv("SKIP_AUTH", raising=False)
        request = MagicMock()
        state = type("State", (), {"user": mock_user})()
        request.state = state
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "8.8.8.8"
        result = await require_tenant(request)
        assert result == mock_user.effective_tenant_id

    async def test_trusted_network_fallback_when_explicitly_configured(self, monkeypatch):
        """The bypass still works — but only when an operator opts in.

        This used to pass with no configuration at all, because TRUSTED_CIDRS
        defaulted to a list containing 10.0.0.0/8. It now requires the operator
        to name BOTH the network (TRUSTED_CIDRS) and the tenant it grants
        (DEFAULT_TENANT_ID), which is the whole point of the change.
        """
        monkeypatch.delenv("SKIP_AUTH", raising=False)
        monkeypatch.setattr(tn_mod, "TRUSTED_NETWORKS", [ipaddress.ip_network("127.0.0.1/32")])
        monkeypatch.setattr(dt_mod, "DEFAULT_TENANT_ID", "0195f48b-d000-7000-8000-000000000001")
        request = MagicMock()
        request.state = type("State", (), {})()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        result = await require_tenant(request)
        assert result == "0195f48b-d000-7000-8000-000000000001"

    async def test_pod_cidr_is_not_trusted_by_default(self, monkeypatch):
        """A k3s pod IP must NOT authenticate itself by being on the pod network.

        Regression test for the live finding of 2026-07-29: TRUSTED_CIDRS
        defaulted to ``...,10.0.0.0/8``, which contains the k3s pod CIDR
        10.42.0.0/16, so every pod in the cluster was granted DEFAULT_TENANT_ID
        instead of a 401. Proven live: an unrelated pod in the `artifacts`
        namespace read coding-containers' /api/containers/ with no credential
        and got HTTP 200 with data.

        This test FAILS against the old default — that is what makes it a real
        regression test rather than a restatement of current behaviour.
        """
        monkeypatch.delenv("SKIP_AUTH", raising=False)
        monkeypatch.delenv("TRUSTED_CIDRS", raising=False)
        assert load_trusted_networks() == [], (
            "TRUSTED_CIDRS must default to empty; a non-empty default is an "
            "authentication bypass for everything inside it"
        )

        request = MagicMock()
        request.state = type("State", (), {})()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "10.42.0.17"  # a k3s pod IP

        monkeypatch.setattr(tn_mod, "TRUSTED_NETWORKS", [])
        with pytest.raises(HTTPException) as exc_info:
            await require_tenant(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.parametrize(
        "host", ["10.42.0.17", "10.0.0.5", "192.168.1.10", "172.16.0.9", "127.0.0.1"]
    )
    def test_no_host_is_trusted_with_empty_config(self, monkeypatch, host):
        """Every address that the old default waved through is now rejected."""
        monkeypatch.setattr(tn_mod, "TRUSTED_NETWORKS", [])
        assert _is_trusted_network(host) is False

    async def test_raises_401_when_nothing_found(self, monkeypatch):
        monkeypatch.delenv("SKIP_AUTH", raising=False)
        request = MagicMock()
        request.state = type("State", (), {})()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "8.8.8.8"

        with patch("coding_client.auth.tenant._is_trusted_network", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await require_tenant(request)
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# License caching
# ---------------------------------------------------------------------------
class TestLicenseCache:
    """Test that license introspection results are cached."""

    async def test_second_call_uses_cache(self):
        _license_cache.clear()
        token = "cached-token-123"
        cache_key = f"lic:{hashlib.sha256(token.encode()).hexdigest()[:16]}"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"active": True, "tenant_id": "cached-tenant"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("coding_client.auth.tenant.httpx.AsyncClient", return_value=mock_client):
            result1 = await _introspect_license(token)
        assert result1["tenant_id"] == "cached-tenant"
        assert cache_key in _license_cache

        # Second call should NOT hit httpx
        mock_client_2 = AsyncMock()
        mock_client_2.post = AsyncMock()
        mock_client_2.__aenter__ = AsyncMock(return_value=mock_client_2)
        mock_client_2.__aexit__ = AsyncMock(return_value=False)

        with patch("coding_client.auth.tenant.httpx.AsyncClient", return_value=mock_client_2):
            result2 = await _introspect_license(token)
        assert result2["tenant_id"] == "cached-tenant"
        mock_client_2.post.assert_not_called()

    async def test_inactive_license_not_cached_as_a_grant(self):
        """An inactive license never enters the POSITIVE cache.

        It does enter the negative one — see
        ``TestFailedIntrospectionsAreNegativeCached`` in
        test_middleware_license.py for why. The distinction is the point: a
        refusal must not be replayable as a grant, and must expire on the short
        clock rather than the 5-minute one.
        """
        _license_cache.clear()
        token = "inactive-token-456"
        cache_key = f"lic:{hashlib.sha256(token.encode()).hexdigest()[:16]}"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"active": False}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("coding_client.auth.tenant.httpx.AsyncClient", return_value=mock_client):
            result = await _introspect_license(token)
        assert result == {"active": False}
        assert cache_key not in _license_cache
        assert cache_key in _negative_license_cache
        assert _negative_license_cache[cache_key] == {"active": False}

    async def test_introspect_returns_none_on_error(self):
        _license_cache.clear()
        token = "error-token"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("network error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("coding_client.auth.tenant.httpx.AsyncClient", return_value=mock_client):
            result = await _introspect_license(token)
        assert result is None

    async def test_a_200_carrying_a_non_dict_body_is_none_not_a_crash(self):
        """`resp.json()` is only as trustworthy as whatever answered the POST.

        A bare string or list would previously have reached `data.get("active")`
        as an AttributeError — swallowed by the broad `except` here, but a crash
        for anyone who later narrowed it. Callers are typed `dict | None`; hold
        the type at the boundary.
        """
        token = "non-dict-body-token"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = ["not", "an", "object"]

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("coding_client.auth.tenant.httpx.AsyncClient", return_value=mock_client):
            result = await _introspect_license(token)
        assert result is None

    async def test_clear_license_caches_empties_both(self):
        """The helper exists so no caller has to remember there are two."""
        _license_cache["lic:positive"] = {"active": True}
        _negative_license_cache["lic:negative"] = None
        clear_license_caches()
        assert len(_license_cache) == 0
        assert len(_negative_license_cache) == 0


# ---------------------------------------------------------------------------
# get_current_user_with_tenant
# ---------------------------------------------------------------------------
class TestGetCurrentUserWithTenant:
    """Test get_current_user_with_tenant dependency."""

    def test_returns_user_with_tenant(self, mock_request, mock_user):
        result = get_current_user_with_tenant(mock_request)
        assert result is mock_user
        assert result.tenant_id is not None

    def test_sets_tenant_to_sub_when_missing(self):
        user = User(sub="u1", preferred_username="a")
        # post_init already sets tenant_id to sub, but let's force-clear it
        user.tenant_id = None
        request = MagicMock()
        request.state.user = user
        result = get_current_user_with_tenant(request)
        assert result.tenant_id == "u1"

    def test_raises_401_when_no_user(self):
        request = MagicMock()
        request.state = type("State", (), {})()
        request.headers = {}
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_with_tenant(request)
        assert exc_info.value.status_code == 401

    def test_raises_401_when_user_is_none(self):
        request = MagicMock()
        request.state.user = None
        request.headers = {}
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_with_tenant(request)
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# require_same_tenant
# ---------------------------------------------------------------------------
class TestRequireSameTenant:
    """Test require_same_tenant dependency factory."""

    def test_admin_can_access_any_tenant(self, admin_user):
        request = MagicMock()
        request.state.user = admin_user
        validator = require_same_tenant("other-tenant-999")
        # Call the inner validator directly with the user (simulating Depends)
        result = validator(user=admin_user)
        assert result is admin_user

    def test_same_tenant_allowed(self, mock_user):
        request = MagicMock()
        request.state.user = mock_user
        validator = require_same_tenant(mock_user.effective_tenant_id)
        result = validator(user=mock_user)
        assert result is mock_user

    def test_different_tenant_denied(self, mock_user):
        validator = require_same_tenant("completely-different-tenant")
        with pytest.raises(HTTPException) as exc_info:
            validator(user=mock_user)
        assert exc_info.value.status_code == 403
        assert "different tenant" in exc_info.value.detail


# ---------------------------------------------------------------------------
# check_tenant_access
# ---------------------------------------------------------------------------
class TestCheckTenantAccess:
    """Test check_tenant_access utility function."""

    def test_admin_returns_true(self, admin_user):
        assert check_tenant_access(admin_user, "any-tenant") is True

    def test_same_tenant_returns_true(self, mock_user):
        assert check_tenant_access(mock_user, mock_user.effective_tenant_id) is True

    def test_different_tenant_returns_false(self, mock_user):
        assert check_tenant_access(mock_user, "other-tenant") is False


# ---------------------------------------------------------------------------
# _is_trusted_network
# ---------------------------------------------------------------------------
class TestIsTrustedNetwork:
    """Test _is_trusted_network helper.

    These four "…_trusted" cases previously asserted that loopback, 192.168/16,
    172.16/12 and **10/8** were trusted with no configuration at all. That was a
    test suite encoding the bug rather than a contract worth keeping: 10/8
    contains the k3s pod CIDR 10.42.0.0/16, so it made every pod in the cluster
    an authenticated caller. They now assert the same addresses are trusted
    *when the operator configures them* — the capability is unchanged, the
    default is not.
    """

    @pytest.fixture(autouse=True)
    def _configured_trusted_networks(self, monkeypatch):
        monkeypatch.setattr(
            tn_mod,
            "TRUSTED_NETWORKS",
            [
                ipaddress.ip_network(c)
                for c in ("127.0.0.1/32", "192.168.0.0/16", "172.16.0.0/12", "10.0.0.0/8")
            ],
        )

    def test_loopback_ipv4_trusted_when_configured(self):
        assert _is_trusted_network("127.0.0.1") is True

    def test_private_192_168_trusted_when_configured(self):
        assert _is_trusted_network("192.168.1.100") is True

    def test_private_172_16_trusted_when_configured(self):
        assert _is_trusted_network("172.16.0.1") is True

    def test_private_10_trusted_when_configured(self):
        assert _is_trusted_network("10.0.0.5") is True

    def test_public_ip_not_trusted(self):
        assert _is_trusted_network("8.8.8.8") is False

    def test_empty_string_not_trusted(self):
        assert _is_trusted_network("") is False

    def test_none_not_trusted(self):
        assert _is_trusted_network(None) is False

    def test_invalid_host_not_trusted(self):
        assert _is_trusted_network("not-an-ip") is False


# ---------------------------------------------------------------------------
# create_tenant_context
# ---------------------------------------------------------------------------
class TestCreateTenantContext:
    """Test create_tenant_context returns tenant context or raises 401."""

    def test_returns_context_when_tenant_available(self):
        request = MagicMock()
        request.state.tenant_id = "t-100"
        result = create_tenant_context(request)
        assert result == {"tenant_id": "t-100"}

    def test_raises_401_when_no_tenant(self):
        request = MagicMock()
        request.state = type("State", (), {})()  # no tenant_id attribute
        request.headers = {}
        with pytest.raises(HTTPException) as exc_info:
            create_tenant_context(request)
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Back-compat surface
# ---------------------------------------------------------------------------
def test_trusted_networks_is_importable_from_tenant_module():
    """`from coding_client.auth.tenant import TRUSTED_NETWORKS` must keep working.

    1.7.0 moved this name to ``._trusted_networks`` and dropped it here. Two
    consumers import it from this module — coding-security
    (``src/auth/tenant.py:22``) and coding-testing (``src/auth/tenant.py:16``) —
    and BOTH wrap their auth-middleware import in
    ``except ImportError: logger.warning("... running WITHOUT authentication ...")``.

    So the missing name would not have failed their build. It would have made
    them boot with no auth middleware at all, announced only as a warning: the
    lockfile bump intended to CLOSE an auth bypass would instead have opened a
    total one. This test is the guard on that.
    """
    from coding_client.auth import _trusted_networks as tn
    from coding_client.auth import tenant as tenant_module

    assert tenant_module.TRUSTED_NETWORKS is tn.TRUSTED_NETWORKS


# ---------------------------------------------------------------------------
# No silent fallback tenant (2026-07-30)
# ---------------------------------------------------------------------------
class TestNoFallbackTenantLiteral:
    """A service with no DEFAULT_TENANT_ID must never serve an invented tenant.

    Every test here FAILS against 1.7.1, where
    ``DEFAULT_TENANT_ID = os.getenv("DEFAULT_TENANT_ID", "n8n-dev")`` meant an
    unconfigured service minted callers against the literal ``"n8n-dev"`` — the
    stale pre-uuid7 label form of a real tenant (canonical id
    ``0195f48b-d000-7000-8000-000000000001`` per the Keycloak TENANT_UUIDS map).

    Each assertion is on the OUTCOME the caller observes (401 / None / no user),
    not on a helper having been called.
    """

    def test_there_is_no_hardcoded_default(self, monkeypatch):
        """The literal is gone from the loader itself."""
        monkeypatch.delenv("DEFAULT_TENANT_ID", raising=False)
        assert load_default_tenant_id() is None, (
            "DEFAULT_TENANT_ID must have NO built-in default; any literal is a "
            "guess about someone else's data isolation"
        )

    @pytest.mark.parametrize("raw", ["", "   ", "\t"])
    def test_blank_is_treated_as_unset(self, monkeypatch, raw):
        """A blank value must not pin callers to an empty tenant."""
        monkeypatch.setenv("DEFAULT_TENANT_ID", raw)
        assert load_default_tenant_id() is None

    def test_resolve_returns_none_and_never_a_literal(self, monkeypatch):
        monkeypatch.setattr(dt_mod, "DEFAULT_TENANT_ID", None)
        assert resolve_default_tenant("a test") is None

    async def test_require_tenant_401s_instead_of_serving_n8n_dev(self, monkeypatch):
        """Trusted network + no configured tenant => 401, NOT "n8n-dev"."""
        monkeypatch.delenv("SKIP_AUTH", raising=False)
        monkeypatch.setattr(tn_mod, "TRUSTED_NETWORKS", [ipaddress.ip_network("127.0.0.1/32")])
        monkeypatch.setattr(dt_mod, "DEFAULT_TENANT_ID", None)

        request = MagicMock()
        request.state = type("State", (), {})()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        with pytest.raises(HTTPException) as exc_info:
            await require_tenant(request)
        assert exc_info.value.status_code == 401
        assert getattr(request.state, "tenant_id", None) is None

    async def test_optional_tenant_returns_none_instead_of_n8n_dev(self, monkeypatch):
        monkeypatch.delenv("SKIP_AUTH", raising=False)
        monkeypatch.setattr(tn_mod, "TRUSTED_NETWORKS", [ipaddress.ip_network("127.0.0.1/32")])
        monkeypatch.setattr(dt_mod, "DEFAULT_TENANT_ID", None)

        request = MagicMock()
        request.state = type("State", (), {})()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        assert await optional_tenant(request) is None
        assert getattr(request.state, "tenant_id", None) is None

    def test_get_current_user_with_tenant_401s_instead_of_minting(self, monkeypatch):
        """No User at all — not a User whose tenant_id backfilled from `sub`.

        ``User.model_post_init`` fills a blank tenant_id from organization_id or
        sub, so building the synthetic user with ``tenant_id=None`` would have
        produced yet another invented tenant instead of a rejection.
        """
        monkeypatch.delenv("SKIP_AUTH", raising=False)
        monkeypatch.setattr(tn_mod, "TRUSTED_NETWORKS", [ipaddress.ip_network("127.0.0.1/32")])
        monkeypatch.setattr(dt_mod, "DEFAULT_TENANT_ID", None)

        request = MagicMock()
        request.state = type("State", (), {})()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        with pytest.raises(HTTPException) as exc_info:
            get_current_user_with_tenant(request)
        assert exc_info.value.status_code == 401

    async def test_configured_tenant_is_served_verbatim(self, monkeypatch):
        """False-positive control: the bypass is not simply dead.

        Without this, every assertion above would still pass if the trusted
        network branch had been deleted outright.
        """
        monkeypatch.delenv("SKIP_AUTH", raising=False)
        monkeypatch.setattr(tn_mod, "TRUSTED_NETWORKS", [ipaddress.ip_network("127.0.0.1/32")])
        monkeypatch.setattr(dt_mod, "DEFAULT_TENANT_ID", "0195f48b-d000-7000-8000-000000000003")

        request = MagicMock()
        request.state = type("State", (), {})()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        assert await require_tenant(request) == "0195f48b-d000-7000-8000-000000000003"
        assert await optional_tenant(request) == "0195f48b-d000-7000-8000-000000000003"
        user = get_current_user_with_tenant(request)
        assert user.tenant_id == "0195f48b-d000-7000-8000-000000000003"


class TestStartupEnforcement:
    """An armed bypass with no tenant to grant must crash boot, not serve one."""

    def test_raises_when_bypass_armed_without_tenant_in_production(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("TRUSTED_CIDRS", "10.0.0.0/8")
        monkeypatch.delenv("DEFAULT_TENANT_ID", raising=False)
        with pytest.raises(RuntimeError) as exc_info:
            enforce_default_tenant_configured()
        assert "DEFAULT_TENANT_ID" in str(exc_info.value)

    def test_error_is_not_an_importerror(self, monkeypatch):
        """coding-security and coding-testing swallow ImportError on this import.

        Both wrap their auth-middleware import in
        ``except ImportError: logger.warning("... running WITHOUT authentication ...")``,
        so raising ImportError here would degrade to exactly the unauthenticated
        boot the check exists to prevent.
        """
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("TRUSTED_CIDRS", "10.0.0.0/8")
        monkeypatch.delenv("DEFAULT_TENANT_ID", raising=False)
        with pytest.raises(RuntimeError) as exc_info:
            enforce_default_tenant_configured()
        assert not isinstance(exc_info.value, ImportError)

    def test_silent_when_bypass_is_disarmed(self, monkeypatch):
        """Today's fleet: TRUSTED_CIDRS empty everywhere => this is a no-op.

        coding-github and coding-repo-jobs set no DEFAULT_TENANT_ID and must
        keep booting.
        """
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("TRUSTED_CIDRS", raising=False)
        monkeypatch.delenv("DEFAULT_TENANT_ID", raising=False)
        enforce_default_tenant_configured()  # must not raise

    def test_silent_when_tenant_is_configured(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("TRUSTED_CIDRS", "10.0.0.0/8")
        monkeypatch.setenv("DEFAULT_TENANT_ID", "0195f48b-d000-7000-8000-000000000001")
        enforce_default_tenant_configured()  # must not raise

    def test_silent_outside_production(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("TRUSTED_CIDRS", "10.0.0.0/8")
        monkeypatch.delenv("DEFAULT_TENANT_ID", raising=False)
        enforce_default_tenant_configured()  # must not raise
