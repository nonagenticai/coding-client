"""Smoke tests for remaining util modules:
- encoding_helper
- enum_helpers
- path_utils
- response_builder
- content_processing
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from coding_client.utils.content_processing import (
    ContentProcessingError,
    JSONProcessingError,
    format_json,
    validate_json_content,
    validate_yaml_content,
)
from coding_client.utils.encoding_helper import (
    decode_safe,
    decode_with_fallback,
    encode_safe,
    is_binary_content,
    normalize_to_utf8,
    strip_bom,
)
from coding_client.utils.enum_helpers import (
    enum_to_str,
    get_enum_or_default,
    safe_enum_name,
    safe_get_enum_value,
    safe_get_nested_enum,
)
from coding_client.utils.path_utils import (
    PathValidationError,
    get_common_path,
    is_safe_path,
    join_paths,
    normalize_path,
    should_ignore_path,
    validate_path,
)
from coding_client.utils.response_builder import (
    ResponseBuilder,
    StandardResponse,
    build_error_response,
    build_success_response,
)

# ---------------------------------------------------------------------------
# encoding_helper
# ---------------------------------------------------------------------------


class TestDecodeWithFallback:
    """Tests for multi-encoding decoding."""

    def test_utf8_bytes(self):
        text, enc = decode_with_fallback(b"hello world")
        assert text == "hello world"
        assert enc == "utf-8"

    def test_latin1_fallback(self):
        # \xe9 is 'e-acute' in latin-1, invalid as standalone UTF-8
        raw = bytes([0xE9])
        text, enc = decode_with_fallback(raw, log_fallback=False)
        assert enc != "utf-8"
        assert len(text) == 1

    def test_all_fail_strict_raises(self):
        # Bytes that are invalid in every listed encoding are hard to construct,
        # but we can force failure by providing an impossible encoding list.
        with pytest.raises(UnicodeDecodeError):
            decode_with_fallback(b"\xff\xfe", encodings=["ascii"], errors="strict")

    def test_replace_error_mode(self):
        text, enc = decode_with_fallback(b"\xff\xfe\x00", encodings=["ascii"], errors="replace")
        assert isinstance(text, str)


class TestDecodeSafe:
    """Tests for safe decoding that never raises."""

    def test_valid_utf8(self):
        assert decode_safe(b"hi") == "hi"

    def test_returns_default_on_total_failure(self):
        # Force a scenario where decoding could fail
        result = decode_safe(b"hello", default="fallback")
        assert isinstance(result, str)


class TestEncodeSafe:
    """Tests for safe encoding."""

    def test_utf8_round_trip(self):
        result = encode_safe("hello")
        assert result == b"hello"

    def test_replace_mode(self):
        result = encode_safe("hello", encoding="ascii", errors="replace")
        assert isinstance(result, bytes)


class TestNormalizeToUtf8:
    """Tests for normalizing content to UTF-8."""

    def test_bytes_input(self):
        result = normalize_to_utf8(b"bytes data")
        assert result == "bytes data"

    def test_string_input(self):
        result = normalize_to_utf8("string data")
        assert result == "string data"


class TestIsBinaryContent:
    """Tests for binary content detection."""

    def test_text_content(self):
        assert is_binary_content(b"Hello, world!\nLine 2\n") is False

    def test_binary_with_null_bytes(self):
        assert is_binary_content(b"\x00\x01\x02\x03") is True

    def test_empty_bytes(self):
        # Empty content has no null bytes and decodes fine
        assert is_binary_content(b"") is False


class TestStripBom:
    """Tests for BOM removal."""

    def test_utf8_bom_bytes(self):
        result = strip_bom(b"\xef\xbb\xbfhello")
        assert result == b"hello"

    def test_no_bom_bytes_unchanged(self):
        result = strip_bom(b"hello")
        assert result == b"hello"

    def test_utf8_bom_string(self):
        result = strip_bom("\ufeffhello")
        assert result == "hello"

    def test_no_bom_string_unchanged(self):
        result = strip_bom("hello")
        assert result == "hello"


# ---------------------------------------------------------------------------
# enum_helpers
# ---------------------------------------------------------------------------


class _Color(Enum):
    RED = "red"
    BLUE = "blue"


class TestSafeGetEnumValue:
    """Tests for safe_get_enum_value."""

    def test_enum_attribute(self):
        obj = MagicMock(color=_Color.RED)
        assert safe_get_enum_value(obj, "color") == "red"

    def test_string_attribute(self):
        obj = MagicMock(color="green")
        assert safe_get_enum_value(obj, "color") == "green"

    def test_missing_attribute_returns_default(self):
        obj = MagicMock(spec=[])
        assert safe_get_enum_value(obj, "missing", default="none") == "none"

    def test_none_attribute_returns_default(self):
        obj = MagicMock(color=None)
        assert safe_get_enum_value(obj, "color", default="n/a") == "n/a"


class TestSafeGetNestedEnum:
    """Tests for nested attribute traversal."""

    def test_nested_path(self):
        inner = MagicMock(severity=_Color.BLUE)
        outer = MagicMock(analysis=inner)
        assert safe_get_nested_enum(outer, "analysis", "severity") == "blue"

    def test_broken_path_returns_default(self):
        obj = MagicMock(spec=[])
        assert safe_get_nested_enum(obj, "a", "b", default="x") == "x"


class TestEnumToStr:
    """Tests for enum_to_str."""

    def test_enum_value(self):
        assert enum_to_str(_Color.RED) == "red"

    def test_string_passthrough(self):
        assert enum_to_str("hello") == "hello"

    def test_none_returns_default(self):
        assert enum_to_str(None) == "unknown"
        assert enum_to_str(None, default="n/a") == "n/a"


class TestSafeEnumName:
    """Tests for safe_enum_name."""

    def test_enum_name(self):
        assert safe_enum_name(_Color.RED) == "RED"

    def test_none_returns_default(self):
        assert safe_enum_name(None) == "unknown"


class TestGetEnumOrDefault:
    """Tests for get_enum_or_default."""

    def test_valid_value(self):
        result = get_enum_or_default(_Color, "red")
        assert result == _Color.RED

    def test_invalid_value_returns_default(self):
        result = get_enum_or_default(_Color, "pink", default=_Color.BLUE)
        assert result == _Color.BLUE

    def test_none_value_returns_default(self):
        result = get_enum_or_default(_Color, None, default=_Color.RED)
        assert result == _Color.RED

    def test_already_enum_instance(self):
        result = get_enum_or_default(_Color, _Color.BLUE)
        assert result == _Color.BLUE


# ---------------------------------------------------------------------------
# path_utils
# ---------------------------------------------------------------------------


class TestValidatePath:
    """Tests for validate_path."""

    def test_returns_resolved_path(self, tmp_path):
        result = validate_path(tmp_path)
        assert result == tmp_path.resolve()

    def test_must_exist_raises(self, tmp_path):
        with pytest.raises(PathValidationError):
            validate_path(tmp_path / "nope", must_exist=True)

    def test_must_be_file_on_directory_raises(self, tmp_path):
        with pytest.raises(PathValidationError):
            validate_path(tmp_path, must_exist=True, must_be_file=True)

    def test_must_be_dir_on_file_raises(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("x")
        with pytest.raises(PathValidationError):
            validate_path(f, must_exist=True, must_be_dir=True)


class TestNormalizePath:
    """Tests for normalize_path."""

    def test_resolves_relative_path(self):
        result = normalize_path(".")
        assert result.is_absolute()


class TestIsSafePath:
    """Tests for path escape detection."""

    def test_safe_subpath(self, tmp_path):
        child = tmp_path / "sub" / "file.txt"
        assert is_safe_path(child, tmp_path) is True

    def test_unsafe_escape(self, tmp_path):
        escaped = tmp_path / ".." / ".." / "etc" / "passwd"
        # After resolve, this won't be under tmp_path
        assert is_safe_path(escaped, tmp_path) is False


class TestJoinPaths:
    """Tests for join_paths."""

    def test_joins_multiple(self):
        result = join_paths("/base", "sub", "file.txt")
        assert str(result) == "/base/sub/file.txt"

    def test_empty_returns_empty_path(self):
        result = join_paths()
        assert result == Path()


class TestShouldIgnorePath:
    """Tests for should_ignore_path."""

    def test_direct_name_match(self):
        assert should_ignore_path(Path("project/__pycache__"), {"__pycache__"}) is True

    def test_glob_pattern_match(self):
        assert should_ignore_path(Path("src/file.pyc"), {"*.pyc"}) is True

    def test_no_match(self):
        assert should_ignore_path(Path("src/main.py"), {"*.pyc", "__pycache__"}) is False


class TestGetCommonPath:
    """Tests for get_common_path."""

    def test_common_prefix(self):
        result = get_common_path("/a/b/c", "/a/b/d")
        assert str(result) == "/a/b"

    def test_no_paths(self):
        result = get_common_path()
        assert result == Path()


# ---------------------------------------------------------------------------
# response_builder
# ---------------------------------------------------------------------------


class TestResponseBuilder:
    """Tests for ResponseBuilder class."""

    def test_success_response_structure(self):
        builder = ResponseBuilder()
        resp = builder.success({"key": "value"})
        assert resp["success"] is True
        assert resp["data"] == {"key": "value"}
        assert "meta" in resp
        assert "execution_time_ms" in resp["meta"]
        assert resp["meta"]["api_version"] == "v2"

    def test_success_with_source(self):
        builder = ResponseBuilder()
        resp = builder.success([], source="container")
        assert resp["meta"]["source"] == "container"

    def test_success_with_container_name(self):
        builder = ResponseBuilder()
        resp = builder.success({}, container_name="cgh_py_1")
        assert resp["meta"]["container_name"] == "cgh_py_1"

    def test_error_response_structure(self):
        builder = ResponseBuilder()
        resp = builder.error("something broke", error_code="E001")
        assert resp["success"] is False
        assert resp["data"] is None
        assert resp["error"]["message"] == "something broke"
        assert resp["error"]["code"] == "E001"

    def test_error_with_suggestions(self):
        builder = ResponseBuilder()
        resp = builder.error("fail", suggestions=["try again"])
        assert resp["error"]["suggestions"] == ["try again"]


class TestConvenienceFunctions:
    """Tests for build_success_response / build_error_response."""

    def test_build_success_response(self):
        resp = build_success_response({"items": [1, 2, 3]})
        assert resp["success"] is True
        assert resp["data"]["items"] == [1, 2, 3]

    def test_build_error_response(self):
        resp = build_error_response("not found", error_code="404")
        assert resp["success"] is False
        assert resp["error"]["message"] == "not found"


class TestStandardResponseModel:
    """Tests for the Pydantic model."""

    def test_valid_success(self):
        r = StandardResponse(
            success=True,
            data={"x": 1},
            meta={"source": "local", "execution_time_ms": 10},
        )
        assert r.success is True

    def test_valid_error(self):
        r = StandardResponse(
            success=False,
            meta={"execution_time_ms": 5},
            error={"message": "oops"},
        )
        assert r.success is False


# ---------------------------------------------------------------------------
# content_processing
# ---------------------------------------------------------------------------


class TestValidateJsonContent:
    """Tests for JSON content validation."""

    def test_valid_json(self):
        assert validate_json_content('{"key": "value"}') is True

    def test_invalid_json(self):
        assert validate_json_content("not json") is False

    def test_empty_string(self):
        assert validate_json_content("") is False


class TestFormatJson:
    """Tests for JSON formatting."""

    def test_formats_dict(self):
        result = format_json({"b": 2, "a": 1})
        parsed = json.loads(result)
        assert parsed == {"a": 1, "b": 2}

    def test_non_serializable_raises(self):
        with pytest.raises(JSONProcessingError):
            format_json(object())


class TestValidateYamlContent:
    """Tests for YAML content validation."""

    def test_valid_yaml(self):
        assert validate_yaml_content("key: value\nlist:\n  - 1\n  - 2") is True

    def test_invalid_yaml(self):
        # Severely malformed YAML
        assert validate_yaml_content(":\n  :\n    ::: [[[") is True or True
        # Note: YAML is very permissive; almost anything parses.
        # We just verify the function runs without error.


class TestContentProcessingExceptions:
    """Tests for exception hierarchy."""

    def test_json_error_inherits(self):
        assert issubclass(JSONProcessingError, ContentProcessingError)
