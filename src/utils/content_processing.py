"""File content processing utilities.

This module provides utilities for processing file content including
JSON/YAML operations, encoding detection, and format-specific handling.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

try:
    import chardet
except ImportError:
    chardet = None
import yaml

from .constants import DEFAULT_ENCODING

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ContentProcessingError(Exception):
    """Base exception for content processing operations."""

    pass


class JSONProcessingError(ContentProcessingError):
    """Raised when JSON processing fails."""

    pass


class YAMLProcessingError(ContentProcessingError):
    """Raised when YAML processing fails."""

    pass


def detect_encoding(file_path: str | Path, sample_size: int = 10000) -> str:
    """Detect file encoding using chardet."""
    path = Path(file_path)

    if chardet is None:
        # If chardet is not available, return default encoding
        return DEFAULT_ENCODING

    try:
        with open(path, "rb") as f:
            sample = f.read(sample_size)

        result = chardet.detect(sample)
        encoding = result.get("encoding")

        if encoding and result.get("confidence", 0) > 0.7:
            return encoding
    except Exception as e:
        logger.warning(f"Error detecting encoding for {path}: {e}")

    return DEFAULT_ENCODING


async def async_detect_encoding(file_path: str | Path, sample_size: int = 10000) -> str:
    """Asynchronously detect file encoding."""
    return await asyncio.to_thread(detect_encoding, file_path, sample_size)


def read_json(
    file_path: str | Path,
    encoding: str = DEFAULT_ENCODING,
    default: Any = None,
) -> Any:
    """Read JSON file with error handling."""
    from .filesystem_ops import FileNotFoundError, read_file

    try:
        content = read_file(file_path, encoding)
        return json.loads(content)
    except FileNotFoundError as e:
        if default is not None:
            logger.warning(f"JSON file not found {file_path}, using default: {e}")
            return default
        raise JSONProcessingError(f"JSON file not found: {file_path}") from e
    except json.JSONDecodeError as e:
        if default is not None:
            logger.warning(f"Invalid JSON in {file_path}, using default: {e}")
            return default
        raise JSONProcessingError(f"Invalid JSON in {file_path}: {e}") from e


async def async_read_json(
    file_path: str | Path,
    encoding: str = DEFAULT_ENCODING,
    default: Any = None,
) -> Any:
    """Asynchronously read JSON file with error handling."""
    return await asyncio.to_thread(read_json, file_path, encoding, default)


def write_json(
    file_path: str | Path,
    data: Any,
    encoding: str = DEFAULT_ENCODING,
    indent: int = 2,
    sort_keys: bool = True,
    create_dirs: bool = True,
) -> Path:
    """Write data to JSON file."""
    from .filesystem_ops import write_file

    try:
        content = json.dumps(data, indent=indent, sort_keys=sort_keys, ensure_ascii=False)
        return write_file(file_path, content, encoding, create_dirs)
    except (TypeError, ValueError) as e:
        raise JSONProcessingError(f"Failed to serialize data to JSON: {e}") from e


async def async_write_json(
    file_path: str | Path,
    data: Any,
    encoding: str = DEFAULT_ENCODING,
    indent: int = 2,
    sort_keys: bool = True,
    create_dirs: bool = True,
) -> Path:
    """Asynchronously write data to JSON file."""
    return await asyncio.to_thread(
        write_json, file_path, data, encoding, indent, sort_keys, create_dirs
    )


def read_yaml(
    file_path: str | Path,
    encoding: str = DEFAULT_ENCODING,
    default: Any = None,
) -> Any:
    """Read YAML file with error handling."""
    from .filesystem_ops import FileNotFoundError, read_file

    try:
        content = read_file(file_path, encoding)
        return yaml.safe_load(content)
    except FileNotFoundError as e:
        if default is not None:
            logger.warning(f"YAML file not found {file_path}, using default: {e}")
            return default
        raise YAMLProcessingError(f"YAML file not found: {file_path}") from e
    except yaml.YAMLError as e:
        if default is not None:
            logger.warning(f"Invalid YAML in {file_path}, using default: {e}")
            return default
        raise YAMLProcessingError(f"Invalid YAML in {file_path}: {e}") from e


async def async_read_yaml(
    file_path: str | Path,
    encoding: str = DEFAULT_ENCODING,
    default: Any = None,
) -> Any:
    """Asynchronously read YAML file with error handling."""
    return await asyncio.to_thread(read_yaml, file_path, encoding, default)


def write_yaml(
    file_path: str | Path,
    data: Any,
    encoding: str = DEFAULT_ENCODING,
    default_flow_style: bool = False,
    create_dirs: bool = True,
) -> Path:
    """Write data to YAML file."""
    from .filesystem_ops import write_file

    try:
        content = yaml.dump(data, default_flow_style=default_flow_style, allow_unicode=True)
        return write_file(file_path, content, encoding, create_dirs)
    except yaml.YAMLError as e:
        raise YAMLProcessingError(f"Failed to serialize data to YAML: {e}") from e


async def async_write_yaml(
    file_path: str | Path,
    data: Any,
    encoding: str = DEFAULT_ENCODING,
    default_flow_style: bool = False,
    create_dirs: bool = True,
) -> Path:
    """Asynchronously write data to YAML file."""
    return await asyncio.to_thread(
        write_yaml, file_path, data, encoding, default_flow_style, create_dirs
    )


def validate_json_content(content: str) -> bool:
    """Validate if string content is valid JSON."""
    try:
        json.loads(content)
        return True
    except (json.JSONDecodeError, TypeError):
        return False


def validate_yaml_content(content: str) -> bool:
    """Validate if string content is valid YAML."""
    try:
        yaml.safe_load(content)
        return True
    except yaml.YAMLError:
        return False


def format_json(
    data: Any,
    indent: int = 2,
    sort_keys: bool = True,
    ensure_ascii: bool = False,
) -> str:
    """Format data as JSON string."""
    try:
        return json.dumps(data, indent=indent, sort_keys=sort_keys, ensure_ascii=ensure_ascii)
    except (TypeError, ValueError) as e:
        raise JSONProcessingError(f"Failed to format as JSON: {e}") from e


def format_yaml(
    data: Any,
    default_flow_style: bool = False,
    allow_unicode: bool = True,
    indent: int = 2,
) -> str:
    """Format data as YAML string."""
    try:
        return yaml.dump(
            data,
            default_flow_style=default_flow_style,
            allow_unicode=allow_unicode,
            indent=indent,
        )
    except yaml.YAMLError as e:
        raise YAMLProcessingError(f"Failed to format as YAML: {e}") from e


def process_files[T](
    directory: str | Path,
    processor: Callable[[Path], T],
    pattern: str = "*",
    recursive: bool = True,
    parallel: bool = False,
    max_workers: int = 4,
) -> list[T]:
    """Process multiple files with a callback function."""
    from .path_utils import list_files

    files = list_files(directory, pattern, recursive)

    if not parallel:
        return [processor(f) for f in files]

    # Parallel processing
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(processor, files))


async def async_process_files[T](
    directory: str | Path,
    processor: Callable[[Path], T],
    pattern: str = "*",
    recursive: bool = True,
    max_concurrent: int = 10,
) -> list[T]:
    """Asynchronously process multiple files."""
    from .path_utils import list_files

    files = await asyncio.to_thread(list_files, directory, pattern, recursive)

    # Create semaphore for concurrency control
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_with_limit(file_path: Path) -> T:
        async with semaphore:
            if inspect.iscoroutinefunction(processor):
                return await processor(file_path)
            else:
                return await asyncio.to_thread(processor, file_path)

    tasks = [process_with_limit(f) for f in files]
    return await asyncio.gather(*tasks)


# Export all public functions
__all__ = [
    # Exceptions
    "ContentProcessingError",
    "JSONProcessingError",
    "YAMLProcessingError",
    # Encoding
    "detect_encoding",
    "async_detect_encoding",
    # JSON operations
    "read_json",
    "async_read_json",
    "write_json",
    "async_write_json",
    "validate_json_content",
    "format_json",
    # YAML operations
    "read_yaml",
    "async_read_yaml",
    "write_yaml",
    "async_write_yaml",
    "validate_yaml_content",
    "format_yaml",
    # Processing
    "process_files",
    "async_process_files",
]
