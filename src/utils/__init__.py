"""Shared utility modules for coding-client.

Provides convenience re-exports from specialized utility modules:
- archive_utils: Backup, temp files, atomic operations
- async_timeout: Async timeout management
- constants: Shared constants
- content_processing: JSON/YAML processing
- database: Database operation utilities
- encoding_helper: Encoding detection and conversion
- enum_helpers: Safe enum value access
- file_operations: Compatibility layer for all file operations
- filesystem_ops: Core filesystem operations
- http_client: HTTP client with retry support
- path_utils: Path validation and manipulation
- profiling: Performance profiling decorators
- response_builder: Standardized API response building
- retry_helper: Retry decorators for docker/network
- security_validation: File security validation
"""

# Submodule re-exports
from . import (
    archive_utils,
    async_timeout,
    constants,
    content_processing,
    database,
    encoding_helper,
    enum_helpers,
    file_operations,
    filesystem_ops,
    http_client,
    path_utils,
    profiling,
    response_builder,
    retry_helper,
    security_validation,
)

# Key items from commonly used modules
from .async_timeout import AsyncTaskManager, AsyncTimeoutError, run_with_timeout, with_timeout
from .http_client import HTTPClient, HTTPClientError
from .response_builder import ResponseBuilder, build_error_response, build_success_response
from .retry_helper import (
    DATABASE_RETRYABLE_EXCEPTIONS,
    RetryConfig,
    RetryHelper,
    retry_database,
    retry_docker,
    retry_network,
)

__all__ = [
    # Submodules
    "archive_utils",
    "async_timeout",
    "constants",
    "content_processing",
    "database",
    "encoding_helper",
    "enum_helpers",
    "file_operations",
    "filesystem_ops",
    "http_client",
    "path_utils",
    "profiling",
    "response_builder",
    "retry_helper",
    "security_validation",
    # Key items
    "DATABASE_RETRYABLE_EXCEPTIONS",
    "AsyncTaskManager",
    "AsyncTimeoutError",
    "build_error_response",
    "build_success_response",
    "HTTPClient",
    "HTTPClientError",
    "ResponseBuilder",
    "RetryConfig",
    "RetryHelper",
    "retry_database",
    "retry_docker",
    "retry_network",
    "run_with_timeout",
    "with_timeout",
]
