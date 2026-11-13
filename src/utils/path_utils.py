"""Path validation and manipulation utilities.

This module provides utilities for path validation, normalization,
pattern matching, and directory operations.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .constants import FROZEN_IGNORE_PATTERNS

logger = logging.getLogger(__name__)


class PathValidationError(Exception):
    """Raised when path validation fails."""

    pass


def validate_path(
    path: str | Path,
    must_exist: bool = False,
    must_be_file: bool = False,
    must_be_dir: bool = False,
) -> Path:
    """Validate and normalize a path.

    Args:
        path: Path to validate
        must_exist: Whether the path must exist
        must_be_file: Whether the path must be a file
        must_be_dir: Whether the path must be a directory

    Returns:
        Normalized Path object

    Raises:
        PathValidationError: If validation fails
    """
    try:
        normalized_path = Path(path).resolve()
    except Exception as e:
        raise PathValidationError(f"Invalid path: {path}") from e

    if must_exist and not normalized_path.exists():
        raise PathValidationError(f"Path does not exist: {normalized_path}")

    if must_be_file and normalized_path.exists() and not normalized_path.is_file():
        raise PathValidationError(f"Path is not a file: {normalized_path}")

    if must_be_dir and normalized_path.exists() and not normalized_path.is_dir():
        raise PathValidationError(f"Path is not a directory: {normalized_path}")

    return normalized_path


def normalize_path(path: str | Path) -> Path:
    """Normalize a path by resolving symlinks and relative components.

    Args:
        path: Path to normalize

    Returns:
        Normalized Path object
    """
    return Path(path).resolve()


def is_safe_path(path: str | Path, base_path: str | Path) -> bool:
    """Check if a path is safe (doesn't escape base directory).

    Args:
        path: Path to check
        base_path: Base directory path

    Returns:
        True if path is safe
    """
    try:
        resolved_path = Path(path).resolve()
        resolved_base = Path(base_path).resolve()

        # Check if the path is within the base directory
        return resolved_path.is_relative_to(resolved_base)
    except Exception:
        return False


def get_relative_path(path: str | Path, base: str | Path) -> Path:
    """Get relative path from base to target.

    Args:
        path: Target path
        base: Base path

    Returns:
        Relative path
    """
    return Path(path).relative_to(base)


def join_paths(*paths: str | Path) -> Path:
    """Join multiple path components safely.

    Args:
        paths: Path components to join

    Returns:
        Joined path
    """
    if not paths:
        return Path()

    result = Path(paths[0])
    for path in paths[1:]:
        result = result / path

    return result


def list_files(
    directory: str | Path,
    pattern: str = "*",
    recursive: bool = False,
    include_hidden: bool = False,
    ignore_patterns: set[str] | frozenset[str] | None = None,
) -> list[Path]:
    """List files in directory with filtering.

    Args:
        directory: Directory path
        pattern: File pattern (glob)
        recursive: Whether to search recursively
        include_hidden: Whether to include hidden files
        ignore_patterns: Patterns to ignore

    Returns:
        List of file paths
    """
    from .filesystem_ops import FileOperationError

    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise FileOperationError(f"Not a directory: {dir_path}")

    if ignore_patterns is None:
        ignore_patterns = FROZEN_IGNORE_PATTERNS

    glob_method = dir_path.rglob if recursive else dir_path.glob
    files = []

    for path in glob_method(pattern):
        if not path.is_file():
            continue

        # Skip hidden files if requested
        if not include_hidden and any(part.startswith(".") for part in path.parts):
            continue

        # Skip ignored patterns
        if should_ignore_path(path, ignore_patterns):
            continue

        files.append(path)

    return sorted(files)


def list_directories(
    directory: str | Path,
    pattern: str = "*",
    recursive: bool = False,
    include_hidden: bool = False,
    ignore_patterns: set[str] | frozenset[str] | None = None,
) -> list[Path]:
    """List directories in directory with filtering.

    Args:
        directory: Directory path
        pattern: Directory pattern (glob)
        recursive: Whether to search recursively
        include_hidden: Whether to include hidden directories
        ignore_patterns: Patterns to ignore

    Returns:
        List of directory paths
    """
    from .filesystem_ops import FileOperationError

    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise FileOperationError(f"Not a directory: {dir_path}")

    if ignore_patterns is None:
        ignore_patterns = FROZEN_IGNORE_PATTERNS

    glob_method = dir_path.rglob if recursive else dir_path.glob
    directories = []

    for path in glob_method(pattern):
        if not path.is_dir():
            continue

        # Skip hidden directories if requested
        if not include_hidden and any(part.startswith(".") for part in path.parts):
            continue

        # Skip ignored patterns
        if should_ignore_path(path, ignore_patterns):
            continue

        directories.append(path)

    return sorted(directories)


def should_ignore_path(path: Path, ignore_patterns: set[str] | frozenset[str]) -> bool:
    """Check if path should be ignored based on patterns.

    Args:
        path: Path to check
        ignore_patterns: Set of patterns to ignore

    Returns:
        True if path should be ignored
    """
    path_str = str(path)

    for pattern in ignore_patterns:
        # Direct name match
        if path.name == pattern:
            return True

        # Pattern match (e.g., *.pyc)
        if pattern.startswith("*") and path.name.endswith(pattern[1:]):
            return True

        # Path contains pattern
        if pattern in path_str:
            return True

    return False


def find_files_by_extension(
    directory: str | Path,
    extensions: str | list[str],
    recursive: bool = True,
) -> list[Path]:
    """Find files by extension(s).

    Args:
        directory: Directory to search
        extensions: File extension(s) to match (with or without dot)
        recursive: Whether to search recursively

    Returns:
        List of matching files
    """
    if isinstance(extensions, str):
        extensions = [extensions]

    # Normalize extensions (ensure they start with dot)
    normalized_exts = []
    for ext in extensions:
        if not ext.startswith("."):
            ext = "." + ext
        normalized_exts.append(ext.lower())

    files = []
    for ext in normalized_exts:
        pattern = f"*{ext}"
        files.extend(list_files(directory, pattern, recursive))

    return sorted(set(files))  # Remove duplicates and sort


def find_files_by_name(
    directory: str | Path,
    names: str | list[str],
    recursive: bool = True,
    case_sensitive: bool = True,
) -> list[Path]:
    """Find files by exact name(s).

    Args:
        directory: Directory to search
        names: File name(s) to match
        recursive: Whether to search recursively
        case_sensitive: Whether matching is case sensitive

    Returns:
        List of matching files
    """
    if isinstance(names, str):
        names = [names]

    if not case_sensitive:
        names = [name.lower() for name in names]

    all_files = list_files(directory, "*", recursive)
    matching_files = []

    for file_path in all_files:
        file_name = file_path.name
        if not case_sensitive:
            file_name = file_name.lower()

        if file_name in names:
            matching_files.append(file_path)

    return sorted(matching_files)


def find_files_containing(
    directory: str | Path,
    text: str,
    file_pattern: str = "*",
    recursive: bool = True,
    case_sensitive: bool = True,
) -> list[Path]:
    """Find files containing specific text in their names.

    Args:
        directory: Directory to search
        text: Text to search for in filenames
        file_pattern: File pattern to match
        recursive: Whether to search recursively
        case_sensitive: Whether search is case sensitive

    Returns:
        List of matching files
    """
    search_text = text if case_sensitive else text.lower()
    all_files = list_files(directory, file_pattern, recursive)
    matching_files = []

    for file_path in all_files:
        file_name = file_path.name
        if not case_sensitive:
            file_name = file_name.lower()

        if search_text in file_name:
            matching_files.append(file_path)

    return sorted(matching_files)


def get_common_path(*paths: str | Path) -> Path:
    """Get common parent path of multiple paths.

    Args:
        paths: Paths to find common parent for

    Returns:
        Common parent path
    """
    if not paths:
        return Path()

    path_objects = [Path(p) for p in paths]

    # Find common parts
    common_parts = []
    if path_objects:
        # Get the minimum number of parts
        min_parts = min(len(p.parts) for p in path_objects)

        for i in range(min_parts):
            part = path_objects[0].parts[i]
            if all(p.parts[i] == part for p in path_objects):
                common_parts.append(part)
            else:
                break

    return Path(*common_parts) if common_parts else Path()


def get_directory_size(directory: str | Path) -> int:
    """Get total size of directory and all its contents.

    Args:
        directory: Directory path

    Returns:
        Total size in bytes
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise PathValidationError(f"Not a directory: {dir_path}")

    total_size = 0
    for file_path in dir_path.rglob("*"):
        if file_path.is_file():
            try:
                total_size += file_path.stat().st_size
            except (OSError, FileNotFoundError):
                # Skip files that can't be accessed
                continue

    return total_size


def is_empty_directory(directory: str | Path) -> bool:
    """Check if directory is empty.

    Args:
        directory: Directory path

    Returns:
        True if directory is empty
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise PathValidationError(f"Not a directory: {dir_path}")

    try:
        next(dir_path.iterdir())
        return False
    except StopIteration:
        return True


def create_directory_tree(base_path: str | Path, structure: dict) -> None:
    """Create directory tree from nested dictionary structure.

    Args:
        base_path: Base directory path
        structure: Nested dict representing directory structure
                  {'dir1': {'subdir1': {}, 'subdir2': {}}, 'dir2': {}}
    """
    base = Path(base_path)

    def _create_dirs(current_path: Path, struct: dict):
        for name, subdirs in struct.items():
            dir_path = current_path / name
            dir_path.mkdir(exist_ok=True)
            if isinstance(subdirs, dict):
                _create_dirs(dir_path, subdirs)

    _create_dirs(base, structure)


# Export all public functions
__all__ = [
    # Exceptions
    "PathValidationError",
    # Validation
    "validate_path",
    "normalize_path",
    "is_safe_path",
    # Path operations
    "get_relative_path",
    "join_paths",
    "get_common_path",
    # Directory listing
    "list_files",
    "list_directories",
    "should_ignore_path",
    # File finding
    "find_files_by_extension",
    "find_files_by_name",
    "find_files_containing",
    # Directory utilities
    "get_directory_size",
    "is_empty_directory",
    "create_directory_tree",
]
