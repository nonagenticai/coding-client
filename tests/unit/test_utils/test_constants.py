"""Tests for coding_client.utils.constants module."""

from __future__ import annotations

import re
from datetime import timedelta

from coding_client.utils.constants import (
    ALLOWED_UPLOAD_EXTENSIONS,
    CACHE_KEY_PREFIX,
    CACHE_TTL_LONG,
    CACHE_TTL_MEDIUM,
    CACHE_TTL_SHORT,
    CACHE_TTL_VERY_LONG,
    CHUNK_SIZE,
    COMPILED_CONTAINER_NAME,
    COMPILED_EMAIL,
    COMPILED_GITHUB_REPO,
    COMPILED_SEMVER,
    COMPILED_URL,
    COMPILED_UUID,
    DEFAULT_BRANCH,
    DEFAULT_ENCODING,
    DEFAULT_PAGE_SIZE,
    FROZEN_IGNORE_PATTERNS,
    FROZEN_SUPPORTED_LANGUAGES,
    GRADE_THRESHOLDS,
    HTTP_RETRY_STATUS_CODES,
    HTTP_TIMEOUT_DEFAULT,
    HTTP_TIMEOUT_LONG,
    HTTP_TIMEOUT_SHORT,
    IGNORE_PATTERNS,
    LANGUAGE_EXTENSIONS,
    MAX_FILE_SIZE,
    MAX_PAGE_SIZE,
    MIN_PAGE_SIZE,
    PRIORITY_NAMES,
    REGEX_EMAIL,
    REGEX_GITHUB_REPO,
    REGEX_SEMVER,
    REGEX_URL,
    REGEX_UUID,
    SUPPORTED_LANGUAGES,
)

# ---------------------------------------------------------------------------
# Type checks
# ---------------------------------------------------------------------------


class TestConstantTypes:
    """Verify that constants are the expected types."""

    def test_http_timeouts_are_floats(self):
        assert isinstance(HTTP_TIMEOUT_DEFAULT, float)
        assert isinstance(HTTP_TIMEOUT_LONG, float)
        assert isinstance(HTTP_TIMEOUT_SHORT, float)

    def test_page_sizes_are_ints(self):
        assert isinstance(DEFAULT_PAGE_SIZE, int)
        assert isinstance(MAX_PAGE_SIZE, int)
        assert isinstance(MIN_PAGE_SIZE, int)

    def test_cache_ttls_are_timedeltas(self):
        assert isinstance(CACHE_TTL_SHORT, timedelta)
        assert isinstance(CACHE_TTL_MEDIUM, timedelta)
        assert isinstance(CACHE_TTL_LONG, timedelta)
        assert isinstance(CACHE_TTL_VERY_LONG, timedelta)

    def test_max_file_size_is_int(self):
        assert isinstance(MAX_FILE_SIZE, int)

    def test_chunk_size_is_int(self):
        assert isinstance(CHUNK_SIZE, int)

    def test_ignore_patterns_is_set(self):
        assert isinstance(IGNORE_PATTERNS, set)

    def test_frozen_ignore_patterns_is_frozenset(self):
        assert isinstance(FROZEN_IGNORE_PATTERNS, frozenset)


# ---------------------------------------------------------------------------
# Value checks
# ---------------------------------------------------------------------------


class TestConstantValues:
    """Verify specific constant values."""

    def test_max_file_size_is_50mb(self):
        assert MAX_FILE_SIZE == 50 * 1024 * 1024

    def test_chunk_size_is_8kb(self):
        assert CHUNK_SIZE == 8192

    def test_default_branch(self):
        assert DEFAULT_BRANCH == "main"

    def test_default_encoding(self):
        assert DEFAULT_ENCODING == "utf-8"

    def test_cache_key_prefix(self):
        assert CACHE_KEY_PREFIX == "cgh:"

    def test_http_retry_status_codes(self):
        assert 429 in HTTP_RETRY_STATUS_CODES
        assert 500 in HTTP_RETRY_STATUS_CODES
        assert 502 in HTTP_RETRY_STATUS_CODES
        assert 503 in HTTP_RETRY_STATUS_CODES
        assert 504 in HTTP_RETRY_STATUS_CODES

    def test_page_size_ordering(self):
        assert MIN_PAGE_SIZE < DEFAULT_PAGE_SIZE < MAX_PAGE_SIZE

    def test_timeout_ordering(self):
        assert HTTP_TIMEOUT_SHORT < HTTP_TIMEOUT_DEFAULT < HTTP_TIMEOUT_LONG


# ---------------------------------------------------------------------------
# LANGUAGE_EXTENSIONS
# ---------------------------------------------------------------------------


class TestLanguageExtensions:
    """Verify language extension mappings."""

    def test_has_python(self):
        assert "python" in LANGUAGE_EXTENSIONS
        assert ".py" in LANGUAGE_EXTENSIONS["python"]

    def test_has_javascript(self):
        assert "javascript" in LANGUAGE_EXTENSIONS
        assert ".js" in LANGUAGE_EXTENSIONS["javascript"]

    def test_has_typescript(self):
        assert "typescript" in LANGUAGE_EXTENSIONS
        assert ".ts" in LANGUAGE_EXTENSIONS["typescript"]

    def test_has_java(self):
        assert "java" in LANGUAGE_EXTENSIONS
        assert ".java" in LANGUAGE_EXTENSIONS["java"]

    def test_has_go(self):
        assert "go" in LANGUAGE_EXTENSIONS
        assert ".go" in LANGUAGE_EXTENSIONS["go"]

    def test_has_rust(self):
        assert "rust" in LANGUAGE_EXTENSIONS
        assert ".rs" in LANGUAGE_EXTENSIONS["rust"]

    def test_supported_languages_matches_keys(self):
        assert SUPPORTED_LANGUAGES == set(LANGUAGE_EXTENSIONS.keys())

    def test_frozen_supported_languages(self):
        assert FROZEN_SUPPORTED_LANGUAGES == frozenset(SUPPORTED_LANGUAGES)

    def test_allowed_upload_extensions_includes_python(self):
        assert ".py" in ALLOWED_UPLOAD_EXTENSIONS


# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------


class TestCompiledRegexPatterns:
    """Ensure regex patterns compile and match expected inputs."""

    def test_email_pattern_compiles(self):
        assert isinstance(COMPILED_EMAIL, re.Pattern)

    def test_email_matches_valid(self):
        assert COMPILED_EMAIL.match("user@example.com")

    def test_email_rejects_invalid(self):
        assert COMPILED_EMAIL.match("not-an-email") is None

    def test_url_pattern_compiles(self):
        assert isinstance(COMPILED_URL, re.Pattern)

    def test_url_matches_https(self):
        assert COMPILED_URL.match("https://example.com")

    def test_github_repo_matches(self):
        assert COMPILED_GITHUB_REPO.match("owner/repo")

    def test_github_repo_rejects_no_slash(self):
        assert COMPILED_GITHUB_REPO.match("justaname") is None

    def test_semver_matches(self):
        assert COMPILED_SEMVER.match("v1.2.3")
        assert COMPILED_SEMVER.match("1.0.0")
        assert COMPILED_SEMVER.match("2.1.0-beta.1")

    def test_uuid_matches(self):
        assert COMPILED_UUID.match("550e8400-e29b-41d4-a716-446655440000")

    def test_uuid_rejects_short(self):
        assert COMPILED_UUID.match("not-a-uuid") is None

    def test_container_name_matches(self):
        assert COMPILED_CONTAINER_NAME.match("my_container.1")

    def test_container_name_rejects_leading_dot(self):
        assert COMPILED_CONTAINER_NAME.match(".bad") is None

    def test_raw_regex_strings_compile(self):
        """All REGEX_* string constants compile without error."""
        for pattern_str in [
            REGEX_EMAIL,
            REGEX_URL,
            REGEX_GITHUB_REPO,
            REGEX_SEMVER,
            REGEX_UUID,
        ]:
            compiled = re.compile(pattern_str)
            assert isinstance(compiled, re.Pattern)


# ---------------------------------------------------------------------------
# Misc lookup structures
# ---------------------------------------------------------------------------


class TestLookupStructures:
    """Tests for grade thresholds, priority names, etc."""

    def test_grade_thresholds_has_a_through_f(self):
        assert set(GRADE_THRESHOLDS.keys()) == {"A", "B", "C", "D", "F"}

    def test_grade_thresholds_are_descending(self):
        values = list(GRADE_THRESHOLDS.values())
        assert values == sorted(values, reverse=True)

    def test_priority_names_mapping(self):
        assert PRIORITY_NAMES[1] == "low"
        assert PRIORITY_NAMES[4] == "critical"
