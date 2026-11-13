"""Common file operation utilities to reduce code duplication.

This module provides reusable file handling functions for reading, writing,
processing, and managing files across the application.

This module now serves as a compatibility layer that imports from specialized modules:
- filesystem_ops: Core file system operations
- path_utils: Path validation and manipulation
- content_processing: File content processing (JSON/YAML, encoding)
- archive_utils: Backup, temp files, and atomic operations
- security_validation: File security and validation
"""

from .archive_utils import (  # Archive and backup operations
    async_atomic_write,
    async_create_backup,
    atomic_write,
    cleanup_temp_files,
    create_backup,
    create_backup_directory,
    create_temp_copy,
    preserve_permissions,
    safe_replace,
    temp_directory,
    temp_file,
)
from .content_processing import (  # Content processing
    async_detect_encoding,
    async_process_files,
    async_read_json,
    async_read_yaml,
    async_write_json,
    async_write_yaml,
    detect_encoding,
    format_json,
    format_yaml,
    process_files,
    read_json,
    read_yaml,
    validate_json_content,
    validate_yaml_content,
    write_json,
    write_yaml,
)

# Import all functions from specialized modules for backward compatibility
from .filesystem_ops import (  # Exceptions; Core file operations
    FileNotFoundError,
    FileOperationError,
    FilePermissionError,
    FileSizeError,
    append_to_file,
    async_read_file,
    async_read_file_chunks,
    async_write_file,
    copy_file,
    delete_directory,
    delete_file,
    ensure_directory,
    move_file,
    read_file,
    read_file_chunks,
    read_file_lines,
    write_file,
)
from .path_utils import (  # Path operations
    create_directory_tree,
    find_files_by_extension,
    find_files_by_name,
    find_files_containing,
    get_directory_size,
    get_relative_path,
    is_empty_directory,
    join_paths,
    list_files,
    normalize_path,
    should_ignore_path,
    validate_path,
)
from .security_validation import (  # Security and validation
    check_file_integrity,
    get_file_hash,
    get_file_info,
    get_file_permissions,
    get_file_size,
    get_safe_temp_dir,
    is_executable_file,
    is_safe_filename,
    sanitize_filename,
    validate_directory_access,
    validate_file_access,
    verify_file_hash,
)

# Export all public functions for backward compatibility
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
    # JSON
    "read_json",
    "async_read_json",
    "write_json",
    "async_write_json",
    "validate_json_content",
    "format_json",
    # YAML
    "read_yaml",
    "async_read_yaml",
    "write_yaml",
    "async_write_yaml",
    "validate_yaml_content",
    "format_yaml",
    # Directory operations
    "ensure_directory",
    "list_files",
    "should_ignore_path",
    "copy_file",
    "move_file",
    "delete_file",
    "delete_directory",
    # Path utilities
    "normalize_path",
    "validate_path",
    "join_paths",
    "get_relative_path",
    "find_files_by_extension",
    "find_files_by_name",
    "find_files_containing",
    "get_directory_size",
    "is_empty_directory",
    "create_directory_tree",
    # Utilities
    "get_file_size",
    "get_file_hash",
    "verify_file_hash",
    "get_file_info",
    "get_file_permissions",
    "detect_encoding",
    "async_detect_encoding",
    # Security and validation
    "validate_file_access",
    "validate_directory_access",
    "check_file_integrity",
    "is_safe_filename",
    "sanitize_filename",
    "is_executable_file",
    "get_safe_temp_dir",
    # Archive and backup
    "create_backup",
    "async_create_backup",
    "create_backup_directory",
    "create_temp_copy",
    "safe_replace",
    "cleanup_temp_files",
    # Context managers
    "temp_file",
    "temp_directory",
    "atomic_write",
    "async_atomic_write",
    "preserve_permissions",
    # Processing
    "process_files",
    "async_process_files",
]
