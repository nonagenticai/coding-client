"""File system operations and management utilities.

This module provides core file system operations including reading, writing,
copying, moving, and deleting files and directories.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import aiofiles

from .constants import CHUNK_SIZE, DEFAULT_ENCODING, MAX_FILE_SIZE

HAS_AIOFILES = True

logger = logging.getLogger(__name__)


class FileOperationError(Exception):
    """Base exception for file operations."""

    pass


class FileSizeError(FileOperationError):
    """Raised when file size exceeds limits."""

    pass


class FileNotFoundError(FileOperationError):
    """Raised when file is not found."""

    pass


class FilePermissionError(FileOperationError):
    """Raised when file permissions prevent operation."""

    pass


def read_file(
    file_path: str | Path,
    encoding: str | None = None,
    max_size: int | None = MAX_FILE_SIZE,
) -> str:
    """Read entire file contents with size validation.

    Args:
        file_path: Path to the file
        encoding: File encoding (auto-detected if None)
        max_size: Maximum allowed file size in bytes

    Returns:
        File contents as string

    Raises:
        FileNotFoundError: If file doesn't exist
        FileSizeError: If file exceeds max_size
        FileOperationError: For other errors
    """
    from .content_processing import detect_encoding
    from .security_validation import validate_file_access

    path = Path(file_path)
    validate_file_access(path, max_size)

    # Auto-detect encoding if not provided
    if encoding is None:
        encoding = detect_encoding(path)

    try:
        with open(path, encoding=encoding) as f:
            return f.read()
    except PermissionError as e:
        raise FilePermissionError(f"Permission denied: {path}") from e
    except Exception as e:
        raise FileOperationError(f"Error reading file {path}: {e}") from e


async def async_read_file(
    file_path: str | Path,
    encoding: str | None = None,
    max_size: int | None = MAX_FILE_SIZE,
) -> str:
    """Asynchronously read entire file contents with size validation.

    Args:
        file_path: Path to the file
        encoding: File encoding (auto-detected if None)
        max_size: Maximum allowed file size in bytes

    Returns:
        File contents as string

    Raises:
        FileNotFoundError: If file doesn't exist
        FileSizeError: If file exceeds max_size
        FileOperationError: For other errors
    """
    from .content_processing import detect_encoding
    from .security_validation import validate_file_access

    path = Path(file_path)
    await asyncio.to_thread(validate_file_access, path, max_size)

    # Auto-detect encoding if not provided
    if encoding is None:
        encoding = await asyncio.to_thread(detect_encoding, path)

    if not HAS_AIOFILES:
        # Fallback to sync read in thread
        return await asyncio.to_thread(read_file, path, encoding, max_size)

    try:
        async with aiofiles.open(path, encoding=encoding) as f:
            return await f.read()
    except PermissionError as e:
        raise FilePermissionError(f"Permission denied: {path}") from e
    except Exception as e:
        raise FileOperationError(f"Error reading file {path}: {e}") from e


def read_file_lines(
    file_path: str | Path,
    encoding: str | None = None,
    skip_empty: bool = False,
    strip_lines: bool = True,
) -> list[str]:
    """Read file and return lines.

    Args:
        file_path: Path to the file
        encoding: File encoding (auto-detected if None)
        skip_empty: Whether to skip empty lines
        strip_lines: Whether to strip whitespace from lines

    Returns:
        List of lines
    """
    content = read_file(file_path, encoding)
    lines = content.splitlines()

    if strip_lines:
        lines = [line.strip() for line in lines]

    if skip_empty:
        lines = [line for line in lines if line]

    return lines


def read_file_chunks(
    file_path: str | Path,
    chunk_size: int = CHUNK_SIZE,
    encoding: str | None = None,
) -> Iterator[str]:
    """Read file in chunks for memory efficiency.

    Args:
        file_path: Path to the file
        chunk_size: Size of each chunk in bytes
        encoding: File encoding (auto-detected if None)

    Yields:
        File chunks
    """
    from .content_processing import detect_encoding

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if encoding is None:
        encoding = detect_encoding(path)

    try:
        with open(path, encoding=encoding) as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
    except Exception as e:
        raise FileOperationError(f"Error reading file {path}: {e}") from e


async def async_read_file_chunks(
    file_path: str | Path,
    chunk_size: int = CHUNK_SIZE,
    encoding: str | None = None,
) -> AsyncIterator[str]:
    """Asynchronously read file in chunks for memory efficiency.

    Args:
        file_path: Path to the file
        chunk_size: Size of each chunk in bytes
        encoding: File encoding (auto-detected if None)

    Yields:
        File chunks
    """
    from .content_processing import detect_encoding

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if encoding is None:
        encoding = await asyncio.to_thread(detect_encoding, path)

    if not HAS_AIOFILES:
        # Fallback to sync read in thread
        def sync_generator() -> list[str]:
            chunks: list[str] = []
            with open(path, encoding=encoding) as f:
                while True:
                    c = f.read(chunk_size)
                    if not c:
                        break
                    chunks.append(c)
            return chunks

        for chunk in await asyncio.to_thread(sync_generator):
            yield chunk
        return

    try:
        async with aiofiles.open(path, encoding=encoding) as f:
            while True:
                chunk = await f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
    except Exception as e:
        raise FileOperationError(f"Error reading file {path}: {e}") from e


def write_file(
    file_path: str | Path,
    content: str,
    encoding: str = DEFAULT_ENCODING,
    create_dirs: bool = True,
    backup: bool = False,
) -> Path:
    """Write content to file with optional backup.

    Args:
        file_path: Path to the file
        content: Content to write
        encoding: File encoding
        create_dirs: Whether to create parent directories
        backup: Whether to create backup of existing file

    Returns:
        Path to the written file
    """
    from .archive_utils import create_backup

    path = Path(file_path)

    # Create parent directories if needed
    if create_dirs:
        path.parent.mkdir(parents=True, exist_ok=True)

    # Create backup if requested and file exists
    if backup and path.exists():
        backup_path = create_backup(path)
        logger.info(f"Created backup: {backup_path}")

    try:
        with open(path, "w", encoding=encoding) as f:
            f.write(content)
        return path
    except PermissionError as e:
        raise FilePermissionError(f"Permission denied: {path}") from e
    except Exception as e:
        raise FileOperationError(f"Error writing file {path}: {e}") from e


async def async_write_file(
    file_path: str | Path,
    content: str,
    encoding: str = DEFAULT_ENCODING,
    create_dirs: bool = True,
    backup: bool = False,
) -> Path:
    """Asynchronously write content to file with optional backup.

    Args:
        file_path: Path to the file
        content: Content to write
        encoding: File encoding
        create_dirs: Whether to create parent directories
        backup: Whether to create backup of existing file

    Returns:
        Path to the written file
    """
    from .archive_utils import create_backup

    path = Path(file_path)

    # Create parent directories if needed
    if create_dirs:
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)

    # Create backup if requested and file exists
    if backup and path.exists():
        backup_path = await asyncio.to_thread(create_backup, path)
        logger.info(f"Created backup: {backup_path}")

    if not HAS_AIOFILES:
        # Fallback to sync write in thread
        return await asyncio.to_thread(write_file, path, content, encoding, create_dirs, backup)

    try:
        async with aiofiles.open(path, "w", encoding=encoding) as f:
            await f.write(content)
        return path
    except PermissionError as e:
        raise FilePermissionError(f"Permission denied: {path}") from e
    except Exception as e:
        raise FileOperationError(f"Error writing file {path}: {e}") from e


def append_to_file(
    file_path: str | Path,
    content: str,
    encoding: str = DEFAULT_ENCODING,
    create_if_missing: bool = True,
) -> Path:
    """Append content to file.

    Args:
        file_path: Path to the file
        content: Content to append
        encoding: File encoding
        create_if_missing: Whether to create file if it doesn't exist

    Returns:
        Path to the file
    """
    path = Path(file_path)

    if not path.exists() and create_if_missing:
        return write_file(path, content, encoding)

    try:
        with open(path, "a", encoding=encoding) as f:
            f.write(content)
        return path
    except Exception as e:
        raise FileOperationError(f"Error appending to file {path}: {e}") from e


def copy_file(
    source: str | Path,
    destination: str | Path,
    create_dirs: bool = True,
    overwrite: bool = True,
) -> Path:
    """Copy file to destination.

    Args:
        source: Source file path
        destination: Destination path
        create_dirs: Whether to create parent directories
        overwrite: Whether to overwrite existing file

    Returns:
        Path to the copied file
    """
    src_path = Path(source)
    dst_path = Path(destination)

    if not src_path.is_file():
        raise FileNotFoundError(f"Source file not found: {src_path}")

    if dst_path.exists() and not overwrite:
        raise FileOperationError(f"Destination already exists: {dst_path}")

    if create_dirs:
        dst_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.copy2(src_path, dst_path)
        return dst_path
    except Exception as e:
        raise FileOperationError(f"Error copying file: {e}") from e


def move_file(
    source: str | Path,
    destination: str | Path,
    create_dirs: bool = True,
) -> Path:
    """Move file to destination.

    Args:
        source: Source file path
        destination: Destination path
        create_dirs: Whether to create parent directories

    Returns:
        Path to the moved file
    """
    src_path = Path(source)
    dst_path = Path(destination)

    if not src_path.exists():
        raise FileNotFoundError(f"Source file not found: {src_path}")

    if create_dirs:
        dst_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.move(str(src_path), str(dst_path))
        return dst_path
    except Exception as e:
        raise FileOperationError(f"Error moving file: {e}") from e


def delete_file(
    file_path: str | Path,
    missing_ok: bool = True,
) -> bool:
    """Delete file safely.

    Args:
        file_path: Path to the file
        missing_ok: Whether to ignore if file doesn't exist

    Returns:
        True if file was deleted, False if it didn't exist
    """
    path = Path(file_path)

    try:
        path.unlink()
        return True
    except FileNotFoundError:
        if missing_ok:
            return False
        raise
    except Exception as e:
        raise FileOperationError(f"Error deleting file: {e}") from e


def delete_directory(
    dir_path: str | Path,
    recursive: bool = True,
    missing_ok: bool = True,
) -> bool:
    """Delete directory safely.

    Args:
        dir_path: Path to the directory
        recursive: Whether to delete recursively
        missing_ok: Whether to ignore if directory doesn't exist

    Returns:
        True if directory was deleted, False if it didn't exist
    """
    path = Path(dir_path)

    if not path.exists():
        if missing_ok:
            return False
        else:
            raise FileNotFoundError(f"Directory not found: {path}")

    try:
        if recursive:
            shutil.rmtree(path)
        else:
            path.rmdir()
        return True
    except Exception as e:
        raise FileOperationError(f"Error deleting directory: {e}") from e


def ensure_directory(path: str | Path) -> Path:
    """Ensure directory exists, creating if necessary.

    Args:
        path: Directory path

    Returns:
        Path object
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


# Export all public functions
__all__ = [
    # Exceptions
    "FileOperationError",
    "FileSizeError",
    "FileNotFoundError",
    "FilePermissionError",
    # Reading
    "read_file",
    "async_read_file",
    "read_file_lines",
    "read_file_chunks",
    "async_read_file_chunks",
    # Writing
    "write_file",
    "async_write_file",
    "append_to_file",
    # File operations
    "copy_file",
    "move_file",
    "delete_file",
    "delete_directory",
    "ensure_directory",
]
