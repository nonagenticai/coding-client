"""Archive and compression utilities.

This module provides utilities for backup creation, temporary file/directory
management, and atomic file operations.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles

from .constants import DEFAULT_ENCODING, TEMP_DIR_PREFIX

HAS_AIOFILES = True

# Remove circular imports - they will be imported locally where needed

logger = __import__("logging").getLogger(__name__)


class ArchiveError(Exception):
    """Base exception for archive operations."""

    pass


class BackupError(ArchiveError):
    """Raised when backup operations fail."""

    pass


class TempFileError(ArchiveError):
    """Raised when temporary file operations fail."""

    pass


def create_backup(
    file_path: str | Path,
    backup_dir: str | Path | None = None,
    timestamp: bool = True,
) -> Path:
    """Create backup of file."""
    from .filesystem_ops import FileNotFoundError

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # Determine backup directory
    if backup_dir:
        backup_dir = Path(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
    else:
        backup_dir = path.parent

    # Create backup filename
    if timestamp:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{path.stem}_backup_{timestamp_str}{path.suffix}"
    else:
        backup_name = f"{path.stem}_backup{path.suffix}"

    backup_path = backup_dir / backup_name

    # Ensure unique filename
    counter = 1
    while backup_path.exists():
        if timestamp:
            backup_name = f"{path.stem}_backup_{timestamp_str}_{counter}{path.suffix}"
        else:
            backup_name = f"{path.stem}_backup_{counter}{path.suffix}"
        backup_path = backup_dir / backup_name
        counter += 1

    try:
        shutil.copy2(path, backup_path)
        return backup_path
    except Exception as e:
        raise BackupError(f"Failed to create backup: {e}") from e


async def async_create_backup(
    file_path: str | Path,
    backup_dir: str | Path | None = None,
    timestamp: bool = True,
) -> Path:
    """Asynchronously create backup of file."""
    return await asyncio.to_thread(create_backup, file_path, backup_dir, timestamp)


def create_backup_directory(
    source_dir: str | Path,
    backup_base: str | Path | None = None,
    timestamp: bool = True,
) -> Path:
    """Create backup of entire directory."""
    from .filesystem_ops import FileOperationError

    source_path = Path(source_dir)
    if not source_path.is_dir():
        raise FileOperationError(f"Not a directory: {source_path}")

    # Determine backup base directory
    if backup_base:
        backup_base = Path(backup_base)
        backup_base.mkdir(parents=True, exist_ok=True)
    else:
        backup_base = source_path.parent

    # Create backup directory name
    if timestamp:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{source_path.name}_backup_{timestamp_str}"
    else:
        backup_name = f"{source_path.name}_backup"

    backup_path = backup_base / backup_name

    # Ensure unique directory name
    counter = 1
    while backup_path.exists():
        if timestamp:
            backup_name = f"{source_path.name}_backup_{timestamp_str}_{counter}"
        else:
            backup_name = f"{source_path.name}_backup_{counter}"
        backup_path = backup_base / backup_name
        counter += 1

    try:
        shutil.copytree(source_path, backup_path)
        return backup_path
    except Exception as e:
        raise BackupError(f"Failed to create directory backup: {e}") from e


@contextmanager
def temp_file(
    suffix: str = "",
    prefix: str = TEMP_DIR_PREFIX,
    dir: str | Path | None = None,
    delete: bool = True,
) -> Iterator[Path]:
    """Context manager for temporary file."""
    try:
        fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=dir)
        os.close(fd)

        path = Path(temp_path)
        try:
            yield path
        finally:
            if delete and path.exists():
                try:
                    path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {path}: {e}")
    except Exception as e:
        raise TempFileError(f"Failed to create temp file: {e}") from e


@contextmanager
def temp_directory(
    suffix: str = "",
    prefix: str = TEMP_DIR_PREFIX,
    dir: str | Path | None = None,
    delete: bool = True,
) -> Iterator[Path]:
    """Context manager for temporary directory."""
    try:
        temp_dir = tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
        path = Path(temp_dir)

        try:
            yield path
        finally:
            if delete and path.exists():
                try:
                    shutil.rmtree(path)
                except Exception as e:
                    logger.warning(f"Failed to delete temp directory {path}: {e}")
    except Exception as e:
        raise TempFileError(f"Failed to create temp directory: {e}") from e


@contextmanager
def atomic_write(
    file_path: str | Path,
    encoding: str = DEFAULT_ENCODING,
    mode: str = "w",
) -> Iterator[Any]:
    """Context manager for atomic file writing."""
    path = Path(file_path)
    temp_path = path.with_suffix(path.suffix + ".tmp")

    try:
        with open(temp_path, mode, encoding=encoding) as f:
            yield f

        # Atomic move on success
        temp_path.replace(path)
    except Exception as e:
        # Clean up temp file on error
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass  # Ignore cleanup errors
        raise TempFileError(f"Atomic write failed: {e}") from e


@asynccontextmanager
async def async_atomic_write(
    file_path: str | Path,
    encoding: str = DEFAULT_ENCODING,
    mode: str = "w",
) -> AsyncIterator[Any]:
    """Async context manager for atomic file writing."""
    if not HAS_AIOFILES:
        raise ImportError("aiofiles module not available - install with 'pip install aiofiles'")

    path = Path(file_path)
    temp_path = path.with_suffix(path.suffix + ".tmp")

    try:
        async with aiofiles.open(temp_path, mode, encoding=encoding) as f:
            yield f

        # Atomic move on success
        await asyncio.to_thread(temp_path.replace, path)
    except Exception as e:
        # Clean up temp file on error
        if temp_path.exists():
            try:
                await asyncio.to_thread(temp_path.unlink)
            except Exception:
                pass  # Ignore cleanup errors
        raise TempFileError(f"Async atomic write failed: {e}") from e


@contextmanager
def preserve_permissions(file_path: str | Path) -> Iterator[None]:
    """Context manager to preserve file permissions during operations."""
    path = Path(file_path)
    original_stat = None

    if path.exists():
        try:
            original_stat = path.stat()
        except Exception:
            pass  # Ignore if we can't get stats

    try:
        yield
    finally:
        if original_stat and path.exists():
            try:
                path.chmod(original_stat.st_mode)
            except Exception as e:
                logger.warning(f"Failed to restore permissions for {path}: {e}")


def create_temp_copy(
    source_path: str | Path,
    suffix: str = "",
    prefix: str = TEMP_DIR_PREFIX,
) -> Path:
    """Create a temporary copy of a file."""
    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {source}")

    try:
        fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
        os.close(fd)

        temp_file_path = Path(temp_path)
        shutil.copy2(source, temp_file_path)
        return temp_file_path
    except Exception as e:
        raise TempFileError(f"Failed to create temp copy: {e}") from e


def safe_replace(
    source: str | Path,
    destination: str | Path,
    backup: bool = True,
) -> Path | None:
    """Safely replace a file with another, optionally creating a backup."""
    from .filesystem_ops import FileNotFoundError

    source_path = Path(source)
    dest_path = Path(destination)

    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    backup_path = None

    try:
        # Create backup if requested and destination exists
        if backup and dest_path.exists():
            backup_path = create_backup(dest_path)

        # Replace the file atomically
        source_path.replace(dest_path)
        return backup_path

    except Exception as e:
        # If we created a backup and replacement failed, try to restore
        if backup_path and backup_path.exists():
            try:
                backup_path.replace(dest_path)
                logger.info(f"Restored backup after failed replacement: {backup_path}")
            except Exception as restore_error:
                logger.error(f"Failed to restore backup: {restore_error}")

        raise ArchiveError(f"Failed to replace file: {e}") from e


def cleanup_temp_files(
    directory: str | Path,
    prefix: str = TEMP_DIR_PREFIX,
    max_age_hours: int = 24,
) -> int:
    """Clean up old temporary files in a directory."""
    import time

    dir_path = Path(directory)
    if not dir_path.is_dir():
        return 0

    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    cleaned_count = 0

    for file_path in dir_path.iterdir():
        if not file_path.name.startswith(prefix):
            continue

        try:
            file_age = current_time - file_path.stat().st_mtime
            if file_age > max_age_seconds:
                if file_path.is_file():
                    file_path.unlink()
                elif file_path.is_dir():
                    shutil.rmtree(file_path)
                cleaned_count += 1
                logger.debug(f"Cleaned up temp file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up {file_path}: {e}")

    return cleaned_count


# Export all public functions
__all__ = [
    # Exceptions
    "ArchiveError",
    "BackupError",
    "TempFileError",
    # Backup operations
    "create_backup",
    "async_create_backup",
    "create_backup_directory",
    # Temporary file/directory operations
    "temp_file",
    "temp_directory",
    "create_temp_copy",
    # Atomic operations
    "atomic_write",
    "async_atomic_write",
    "safe_replace",
    # Utilities
    "preserve_permissions",
    "cleanup_temp_files",
]
