"""
Encoding helper utilities for handling text encoding/decoding.

This module centralizes encoding operations to reduce cyclomatic complexity
across services that handle file content (github_integration_service, etc.).
"""

import logging

logger = logging.getLogger(__name__)

# Default encoding fallback chain
DEFAULT_ENCODINGS: list[str] = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]


def decode_with_fallback(
    content: bytes,
    encodings: list[str] | None = None,
    errors: str = "strict",
    log_fallback: bool = True,
) -> tuple[str, str]:
    """
    Decode bytes to string, trying multiple encodings.

    Args:
        content: Bytes to decode
        encodings: List of encodings to try (default: utf-8, latin-1, cp1252, iso-8859-1)
        errors: Error handling mode for final attempt ('strict', 'replace', 'ignore')
        log_fallback: Whether to log when falling back to non-utf8 encoding

    Returns:
        Tuple of (decoded_string, encoding_used)

    Raises:
        UnicodeDecodeError: If all encodings fail and errors='strict'

    Example:
        # Instead of:
        # try:
        #     content = content.decode("utf-8")
        # except UnicodeDecodeError:
        #     for encoding in ["latin-1", "cp1252", "iso-8859-1"]:
        #         try:
        #             content = content.decode(encoding)
        #             break
        #         except UnicodeDecodeError:
        #             continue

        # Use:
        content, encoding = decode_with_fallback(raw_bytes)
    """
    if encodings is None:
        encodings = DEFAULT_ENCODINGS.copy()

    last_error: UnicodeDecodeError | None = None

    for encoding in encodings:
        try:
            decoded = content.decode(encoding)
            if encoding != "utf-8" and log_fallback:
                logger.debug(f"Decoded content using fallback encoding: {encoding}")
            return decoded, encoding
        except UnicodeDecodeError as e:
            last_error = e
            continue

    # If all encodings failed, try with error handling
    if errors != "strict":
        try:
            decoded = content.decode("utf-8", errors=errors)
            logger.warning(f"Decoded content with error handling mode: {errors}")
            return decoded, f"utf-8-{errors}"
        except UnicodeDecodeError:
            pass

    # Raise the last error if nothing worked
    if last_error:
        raise last_error
    raise UnicodeDecodeError("utf-8", content, 0, len(content), "All encodings failed")


def decode_safe(
    content: bytes,
    encodings: list[str] | None = None,
    default: str = "",
) -> str:
    """
    Safely decode bytes to string, returning default on failure.

    Args:
        content: Bytes to decode
        encodings: List of encodings to try
        default: Value to return if decoding fails

    Returns:
        Decoded string or default

    Example:
        content = decode_safe(raw_bytes, default="<binary content>")
    """
    try:
        decoded, _ = decode_with_fallback(content, encodings, errors="replace")
        return decoded
    except Exception:
        return default


def encode_safe(
    content: str,
    encoding: str = "utf-8",
    errors: str = "replace",
) -> bytes:
    """
    Safely encode string to bytes with error handling.

    Args:
        content: String to encode
        encoding: Target encoding
        errors: Error handling mode ('strict', 'replace', 'ignore', 'xmlcharrefreplace')

    Returns:
        Encoded bytes

    Example:
        # Instead of:
        # content = content.encode("utf-8", errors="replace").decode("utf-8")
        # Use:
        safe_bytes = encode_safe(content)
    """
    return content.encode(encoding, errors=errors)


def normalize_to_utf8(content: str | bytes) -> str:
    """
    Normalize content to UTF-8 string, handling both bytes and strings.

    Args:
        content: String or bytes to normalize

    Returns:
        UTF-8 normalized string

    Example:
        text = normalize_to_utf8(possibly_bytes_or_string)
    """
    if isinstance(content, bytes):
        decoded, _ = decode_with_fallback(content, errors="replace")
        return decoded
    return content.encode("utf-8", errors="replace").decode("utf-8")


def is_binary_content(content: bytes, sample_size: int = 8192) -> bool:
    """
    Detect if content appears to be binary (non-text).

    Args:
        content: Bytes to check
        sample_size: Number of bytes to sample for detection

    Returns:
        True if content appears to be binary

    Example:
        if is_binary_content(file_bytes):
            logger.info("Skipping binary file")
    """
    # Check for null bytes (common indicator of binary)
    sample = content[:sample_size]
    if b"\x00" in sample:
        return True

    # Try to decode as UTF-8
    try:
        sample.decode("utf-8")
        return False
    except UnicodeDecodeError:
        pass

    # Try common text encodings
    for encoding in ["latin-1", "cp1252"]:
        try:
            decoded = sample.decode(encoding)
            # Check for high ratio of control characters (likely binary)
            control_chars = sum(1 for c in decoded if ord(c) < 32 and c not in "\n\r\t")
            if control_chars / len(decoded) > 0.1:
                return True
            return False
        except UnicodeDecodeError:
            continue

    return True


def strip_bom(content: str | bytes) -> str | bytes:
    """
    Remove BOM (Byte Order Mark) from content.

    Args:
        content: String or bytes that may contain BOM

    Returns:
        Content with BOM removed

    Example:
        clean_content = strip_bom(file_content)
    """
    if isinstance(content, bytes):
        # UTF-8 BOM
        if content.startswith(b"\xef\xbb\xbf"):
            return content[3:]
        # UTF-16 BOMs
        if content.startswith((b"\xff\xfe", b"\xfe\xff")):
            return content[2:]
        # UTF-32 BOMs
        if content.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
            return content[4:]
        return content

    # String version
    if content.startswith("\ufeff"):
        return content[1:]
    return content
