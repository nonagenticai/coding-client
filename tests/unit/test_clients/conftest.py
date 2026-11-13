"""Shared fixtures for service-client tests.

The clients no longer carry hardcoded fallback URLs (config-externalization
policy: the platform configuration policy). Tests that
construct a client with no explicit ``base_url=`` rely on the env vars below
being set; the dedicated "raises when unset" tests clear them via monkeypatch.
"""

from __future__ import annotations

import pytest

# Test URLs match the values asserted in test_service_clients.py for the
# "no override" cases — they're not real DNS, just non-empty strings that
# satisfy the constructor's required-URL check.
_DEFAULT_TEST_ENV: dict[str, str] = {
    "CODING_AI_URL": "http://coding-ai:8690",
    "CODING_ANALYSIS_URL": "http://coding-analysis:8688",
    "CODING_CONTAINERS_URL": "http://coding-containers:8691",
    "CODING_GITHUB_URL": "http://coding-github:8692",
    "CODING_REALTIME_URL": "http://coding-realtime:8694",
    "CODING_SECURITY_URL": "http://coding-security:8693",
    "CODING_TESTING_URL": "http://coding-testing:8689",
}


@pytest.fixture(autouse=True)
def _service_client_default_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Populate per-service URL env vars for every test in this package.

    Tests that need to assert the "missing config raises" path use
    ``monkeypatch.delenv(..., raising=False)`` to opt out.
    """
    for key, value in _DEFAULT_TEST_ENV.items():
        monkeypatch.setenv(key, value)
