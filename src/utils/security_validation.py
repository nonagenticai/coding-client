"""File security and validation utilities.

This module provides utilities for file security validation, size checks,
hash calculations, and permission validation.
"""

from __future__ import annotations

import hashlib
import logging
import os
import stat
from datetime import datetime
from pathlib import Path
from typing import Any

from .constants import CHUNK_SIZE, MAX_FILE_SIZE

logger = logging.getLogger(__name__)


class SecurityValidationError(Exception):
    """Base exception for security validation operations."""

    pass


class FileSizeError(SecurityValidationError):
    """Raised when file size exceeds limits."""

    pass


class FilePermissionError(SecurityValidationError):
    """Raised when file permissions prevent operation."""

    pass


class FileNotFoundError(SecurityValidationError):
    """Raised when file is not found."""

    pass


class InvalidPathError(SecurityValidationError):
    """Raised when path is invalid or unsafe."""

    pass


def validate_file_access(
    file_path: str | Path,
    max_size: int | None = MAX_FILE_SIZE,
    check_readable: bool = True,
    check_writable: bool = False,
) -> None:
    """Validate file access and basic security checks."""
    path = Path(file_path)

    # Check if file exists
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # Check if it's actually a file
    if not path.is_file():
        raise InvalidPathError(f"Not a file: {path}")

    # Check file size
    if max_size is not None:
        file_size = path.stat().st_size
        if file_size > max_size:
            raise FileSizeError(f"File too large: {file_size} bytes (max: {max_size})")

    # Check permissions
    if check_readable and not os.access(path, os.R_OK):
        raise FilePermissionError(f"File not readable: {path}")

    if check_writable and not os.access(path, os.W_OK):
        raise FilePermissionError(f"File not writable: {path}")


def validate_directory_access(
    dir_path: str | Path,
    check_readable: bool = True,
    check_writable: bool = False,
    check_executable: bool = True,
) -> None:
    """Validate directory access and permissions."""
    path = Path(dir_path)

    # Check if directory exists
    if not path.exists():
        raise FileNotFoundError(f"Directory not found: {path}")

    # Check if it's actually a directory
    if not path.is_dir():
        raise InvalidPathError(f"Not a directory: {path}")

    # Check permissions
    if check_readable and not os.access(path, os.R_OK):
        raise FilePermissionError(f"Directory not readable: {path}")

    if check_writable and not os.access(path, os.W_OK):
        raise FilePermissionError(f"Directory not writable: {path}")

    if check_executable and not os.access(path, os.X_OK):
        raise FilePermissionError(f"Directory not executable: {path}")


def get_file_size(file_path: str | Path) -> int:
    """Get file size in bytes."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    try:
        return path.stat().st_size
    except Exception as e:
        raise SecurityValidationError(f"Failed to get file size: {e}") from e


def get_file_hash(
    file_path: str | Path,
    algorithm: str = "sha256",
    chunk_size: int = CHUNK_SIZE,
) -> str:
    """Calculate file hash."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    try:
        hash_obj = hashlib.new(algorithm)

        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                hash_obj.update(chunk)

        return hash_obj.hexdigest()
    except Exception as e:
        raise SecurityValidationError(f"Failed to calculate hash: {e}") from e


def verify_file_hash(
    file_path: str | Path,
    expected_hash: str,
    algorithm: str = "sha256",
) -> bool:
    """Verify file hash matches expected value."""
    try:
        actual_hash = get_file_hash(file_path, algorithm)
        return actual_hash.lower() == expected_hash.lower()
    except Exception as e:
        raise SecurityValidationError(f"Hash verification failed: {e}") from e


def get_file_permissions(file_path: str | Path) -> dict[str, bool]:
    """Get file permission details."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    try:
        file_stat = path.stat()
        mode = file_stat.st_mode

        return {
            "owner_read": bool(mode & stat.S_IRUSR),
            "owner_write": bool(mode & stat.S_IWUSR),
            "owner_execute": bool(mode & stat.S_IXUSR),
            "group_read": bool(mode & stat.S_IRGRP),
            "group_write": bool(mode & stat.S_IWGRP),
            "group_execute": bool(mode & stat.S_IXGRP),
            "other_read": bool(mode & stat.S_IROTH),
            "other_write": bool(mode & stat.S_IWOTH),
            "other_execute": bool(mode & stat.S_IXOTH),
            "is_suid": bool(mode & stat.S_ISUID),
            "is_sgid": bool(mode & stat.S_ISGID),
            "is_sticky": bool(mode & stat.S_ISVTX),
        }
    except Exception as e:
        raise SecurityValidationError(f"Failed to get permissions: {e}") from e


def is_safe_filename(filename: str) -> bool:
    """Check if filename is safe (no path traversal, etc.)."""
    # Check for empty or None
    if not filename:
        return False

    # Check for path separators
    if os.sep in filename or os.altsep and os.altsep in filename:
        return False

    # Check for current/parent directory references
    if filename in (".", ".."):
        return False

    # Check for null bytes
    if "\x00" in filename:
        return False

    # Check for control characters
    if any(ord(char) < 32 for char in filename):
        return False

    # Check for reserved names on Windows
    reserved_names = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }

    name_upper = filename.upper()
    if name_upper in reserved_names or name_upper.split(".")[0] in reserved_names:
        return False

    return True


def sanitize_filename(filename: str, replacement: str = "_") -> str:
    """Sanitize filename by replacing unsafe characters."""
    if not filename:
        return "unnamed"

    # Replace path separators
    safe_name = filename.replace(os.sep, replacement)
    if os.altsep:
        safe_name = safe_name.replace(os.altsep, replacement)

    # Replace control characters and null bytes
    safe_chars = []
    for char in safe_name:
        if ord(char) < 32 or char == "\x00":
            safe_chars.append(replacement)
        else:
            safe_chars.append(char)

    safe_name = "".join(safe_chars)

    # Handle reserved names
    reserved_names = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }

    name_upper = safe_name.upper()
    if name_upper in reserved_names or name_upper.split(".")[0] in reserved_names:
        safe_name = f"file_{safe_name}"

    # Ensure not empty after sanitization
    if not safe_name or safe_name == replacement:
        safe_name = "unnamed"

    return safe_name


def get_file_info(file_path: str | Path) -> dict[str, Any]:
    """Get comprehensive file information including security details."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    try:
        file_stat = path.stat()

        return {
            "path": str(path.absolute()),
            "name": path.name,
            "size": file_stat.st_size,
            "created": datetime.fromtimestamp(file_stat.st_ctime),
            "modified": datetime.fromtimestamp(file_stat.st_mtime),
            "accessed": datetime.fromtimestamp(file_stat.st_atime),
            "is_file": path.is_file(),
            "is_dir": path.is_dir(),
            "is_symlink": path.is_symlink(),
            "suffix": path.suffix,
            "suffixes": path.suffixes,
            "stem": path.stem,
            "parent": str(path.parent),
            "permissions": get_file_permissions(path),
            "owner_uid": file_stat.st_uid,
            "group_gid": file_stat.st_gid,
            "mode_octal": oct(file_stat.st_mode),
            "inode": file_stat.st_ino,
            "device": file_stat.st_dev,
            "nlinks": file_stat.st_nlink,
        }
    except Exception as e:
        raise SecurityValidationError(f"Failed to get file info: {e}") from e


def check_file_integrity(
    file_path: str | Path,
    expected_size: int | None = None,
    expected_hash: str | None = None,
    hash_algorithm: str = "sha256",
) -> dict[str, bool | None]:
    """Check file integrity against expected values."""
    results = {
        "exists": False,
        "size_match": None,
        "hash_match": None,
        "overall_valid": False,
    }

    path = Path(file_path)

    # Check if file exists
    if not path.exists():
        return results

    results["exists"] = True

    try:
        # Check size if provided
        if expected_size is not None:
            actual_size = get_file_size(path)
            results["size_match"] = actual_size == expected_size

        # Check hash if provided
        if expected_hash is not None:
            results["hash_match"] = verify_file_hash(path, expected_hash, hash_algorithm)

        # Overall validity
        checks = [v for v in results.values() if v is not None and isinstance(v, bool)]
        results["overall_valid"] = all(checks) if checks else True

        return results
    except Exception as e:
        raise SecurityValidationError(f"Integrity check failed: {e}") from e


def is_executable_file(file_path: str | Path) -> bool:
    """Check if file is executable."""
    path = Path(file_path)
    return path.exists() and os.access(path, os.X_OK)


def get_safe_temp_dir() -> Path:
    """Get a safe temporary directory with appropriate permissions."""
    import tempfile

    try:
        temp_dir = Path(tempfile.gettempdir())

        # Verify temp directory is safe
        if not temp_dir.exists():
            raise SecurityValidationError("System temp directory doesn't exist")

        if not os.access(temp_dir, os.R_OK | os.W_OK | os.X_OK):
            raise SecurityValidationError("Insufficient permissions on temp directory")

        return temp_dir
    except Exception as e:
        raise SecurityValidationError(f"Failed to get safe temp directory: {e}") from e


# Export all public functions
__all__ = [
    # Exceptions
    "SecurityValidationError",
    "FileSizeError",
    "FilePermissionError",
    "FileNotFoundError",
    "InvalidPathError",
    # Validation
    "validate_file_access",
    "validate_directory_access",
    # File info
    "get_file_size",
    "get_file_info",
    "get_file_permissions",
    # Hashing
    "get_file_hash",
    "verify_file_hash",
    # Security checks
    "is_safe_filename",
    "sanitize_filename",
    "check_file_integrity",
    "is_executable_file",
    "get_safe_temp_dir",
]
