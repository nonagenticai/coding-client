"""Shared constants and configuration values used across the application.

This module centralizes commonly used constants, configuration values, and
magic numbers to avoid duplication and improve maintainability.
"""

from __future__ import annotations

import re
from datetime import timedelta

# HTTP Related Constants
HTTP_TIMEOUT_DEFAULT = 30.0  # seconds
HTTP_TIMEOUT_LONG = 300.0  # 5 minutes for long operations
HTTP_TIMEOUT_SHORT = 10.0  # Quick operations
HTTP_RETRY_COUNT = 3
HTTP_RETRY_BACKOFF = 0.3
HTTP_RETRY_STATUS_CODES = [429, 500, 502, 503, 504]

# API Response Headers
HEADERS_JSON = {"Content-Type": "application/json"}
HEADERS_ACCEPT_JSON = {"Accept": "application/json"}
HEADERS_GITHUB = {"Accept": "application/vnd.github.v3+json"}

# Pagination Constants
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MIN_PAGE_SIZE = 1
DEFAULT_PAGE_NUMBER = 1

# Cache Configuration
CACHE_TTL_SHORT = timedelta(minutes=5)
CACHE_TTL_MEDIUM = timedelta(minutes=30)
CACHE_TTL_LONG = timedelta(hours=1)
CACHE_TTL_VERY_LONG = timedelta(hours=24)
CACHE_KEY_PREFIX = "cgh:"  # code_graph_helper

# File Operation Constants
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
CHUNK_SIZE = 8192  # 8KB chunks for file reading
TEMP_DIR_PREFIX = "cgh_temp_"
LOG_FILE_EXTENSION = ".log"
JSON_FILE_EXTENSION = ".json"

# Path Patterns
IGNORE_PATTERNS = {
    "__pycache__",
    ".git",
    ".idea",
    ".vscode",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    "*.pyc",
    "*.pyo",
    ".DS_Store",
    "Thumbs.db",
    ".env",
    ".env.*",
    "venv",
    "env",
    ".venv",
}

# File Extensions by Language
PYTHON_EXTENSIONS = {".py", ".pyw", ".pyi"}
JAVASCRIPT_EXTENSIONS = {".js", ".jsx", ".mjs"}
TYPESCRIPT_EXTENSIONS = {".ts", ".tsx", ".d.ts"}
JAVA_EXTENSIONS = {".java"}
GO_EXTENSIONS = {".go"}
RUST_EXTENSIONS = {".rs"}
C_EXTENSIONS = {".c", ".h"}
CPP_EXTENSIONS = {".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"}
CSHARP_EXTENSIONS = {".cs"}
RUBY_EXTENSIONS = {".rb"}
PHP_EXTENSIONS = {".php"}
SWIFT_EXTENSIONS = {".swift"}
KOTLIN_EXTENSIONS = {".kt", ".kts"}

# Language Mapping
LANGUAGE_EXTENSIONS: dict[str, set[str]] = {
    "python": PYTHON_EXTENSIONS,
    "javascript": JAVASCRIPT_EXTENSIONS,
    "typescript": TYPESCRIPT_EXTENSIONS,
    "java": JAVA_EXTENSIONS,
    "go": GO_EXTENSIONS,
    "rust": RUST_EXTENSIONS,
    "c": C_EXTENSIONS,
    "cpp": CPP_EXTENSIONS,
    "csharp": CSHARP_EXTENSIONS,
    "ruby": RUBY_EXTENSIONS,
    "php": PHP_EXTENSIONS,
    "swift": SWIFT_EXTENSIONS,
    "kotlin": KOTLIN_EXTENSIONS,
}

# Supported Languages
SUPPORTED_LANGUAGES = set(LANGUAGE_EXTENSIONS.keys())

# Database Constants
DB_POOL_SIZE = 20
DB_MAX_OVERFLOW = 10
DB_POOL_TIMEOUT = 30
DB_ECHO = False
DB_TRANSACTION_TIMEOUT = 60  # seconds

# Container Configuration
CONTAINER_BASE_PORT = 8700
CONTAINER_PORT_RANGE = 100  # Ports 8700-8799
CONTAINER_HEALTH_CHECK_INTERVAL = 5  # seconds
CONTAINER_HEALTH_CHECK_TIMEOUT = 30  # seconds
CONTAINER_HEALTH_CHECK_RETRIES = 6
CONTAINER_STOP_TIMEOUT = 10  # seconds
CONTAINER_NAME_PREFIX = "cgh_"
CONTAINER_LABEL_PREFIX = "com.codegraphhelper"

# Docker Constants
DOCKER_IMAGE_NAME = "code_graph_helper-api:latest"
DOCKER_NETWORK_NAME = "code_graph_network"
DOCKER_VOLUME_PREFIX = "cgh_volume_"
DOCKER_BUILD_TIMEOUT = 600  # 10 minutes
DOCKER_PULL_TIMEOUT = 300  # 5 minutes

# Quality Analysis Constants
MAX_FUNCTION_LENGTH = 50  # lines
MAX_FILE_LENGTH = 500  # lines
MAX_CYCLOMATIC_COMPLEXITY = 10
MAX_COGNITIVE_COMPLEXITY = 15
MAX_PARAMETERS = 5
MAX_NESTING_DEPTH = 4
MIN_FUNCTION_NAME_LENGTH = 3
MAX_LINE_LENGTH = 120

# Security Constants
MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_UPLOAD_EXTENSIONS = {
    *PYTHON_EXTENSIONS,
    *JAVASCRIPT_EXTENSIONS,
    *TYPESCRIPT_EXTENSIONS,
    *JAVA_EXTENSIONS,
    *GO_EXTENSIONS,
    *RUST_EXTENSIONS,
    *C_EXTENSIONS,
    *CPP_EXTENSIONS,
    ".txt",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
}

# API Rate Limiting
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_BURST = 20

# Webhook Configuration
WEBHOOK_TIMEOUT = 30  # seconds
WEBHOOK_MAX_RETRIES = 3
WEBHOOK_RETRY_DELAY = 5  # seconds
WEBHOOK_SIGNATURE_HEADER = "X-Hub-Signature-256"
WEBHOOK_EVENT_HEADER = "X-GitHub-Event"

# GitHub Integration
GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
GITHUB_MAX_FILE_SIZE = 1024 * 1024  # 1MB for API
GITHUB_PER_PAGE = 100  # Max items per page
GITHUB_MAX_SEARCH_RESULTS = 1000

# Testing Constants
TEST_TIMEOUT_DEFAULT = 300  # 5 minutes
TEST_TIMEOUT_LONG = 600  # 10 minutes
TEST_RETRY_COUNT = 2
TEST_PARALLEL_WORKERS = 4
TEST_COVERAGE_THRESHOLD = 80.0  # percent

# Logging Configuration
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5
LOG_ENCODING = "utf-8"

# Analysis Constants
ANALYSIS_BATCH_SIZE = 100
ANALYSIS_WORKER_COUNT = 4
ANALYSIS_QUEUE_SIZE = 1000
ANALYSIS_TIMEOUT = 300  # 5 minutes per file

# Graph Database Constants
NEO4J_BATCH_SIZE = 1000
NEO4J_CONNECTION_TIMEOUT = 30
NEO4J_MAX_CONNECTION_LIFETIME = 3600  # 1 hour
NEO4J_MAX_CONNECTION_POOL_SIZE = 50

# Redis Configuration
REDIS_KEY_SEPARATOR = ":"
REDIS_LOCK_TIMEOUT = 60  # seconds
REDIS_LOCK_RETRY_DELAY = 0.1  # seconds
REDIS_PIPELINE_SIZE = 100

# Error Messages
ERROR_INVALID_PARAMETER = "Invalid parameter: {parameter}"
ERROR_NOT_FOUND = "{resource} not found"
ERROR_ALREADY_EXISTS = "{resource} already exists"
ERROR_PERMISSION_DENIED = "Permission denied for {resource}"
ERROR_OPERATION_FAILED = "{operation} failed: {reason}"
ERROR_VALIDATION_FAILED = "Validation failed: {details}"
ERROR_TIMEOUT = "Operation timed out after {timeout} seconds"
ERROR_RATE_LIMITED = "Rate limit exceeded. Try again in {retry_after} seconds"

# Success Messages
SUCCESS_CREATED = "{resource} created successfully"
SUCCESS_UPDATED = "{resource} updated successfully"
SUCCESS_DELETED = "{resource} deleted successfully"
SUCCESS_OPERATION_COMPLETED = "{operation} completed successfully"

# Regular Expression Patterns
REGEX_EMAIL = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
REGEX_URL = r"^https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)$"
REGEX_GITHUB_REPO = r"^[\w.-]+/[\w.-]+$"
REGEX_SEMVER = r"^v?\d+\.\d+\.\d+(?:-[\w.]+)?(?:\+[\w.]+)?$"
REGEX_UUID = r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
REGEX_CONTAINER_NAME = r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$"

# MIME Types
MIME_TYPE_JSON = "application/json"
MIME_TYPE_TEXT = "text/plain"
MIME_TYPE_HTML = "text/html"
MIME_TYPE_XML = "application/xml"
MIME_TYPE_YAML = "application/yaml"
MIME_TYPE_OCTET_STREAM = "application/octet-stream"

# Status Codes (custom ones, standard HTTP codes should be imported from http.HTTPStatus)
STATUS_PROCESSING = 102
STATUS_MULTI_STATUS = 207
STATUS_ALREADY_REPORTED = 208
STATUS_IM_USED = 226

# Time Formats
TIME_FORMAT_ISO = "%Y-%m-%dT%H:%M:%SZ"
TIME_FORMAT_HUMAN = "%Y-%m-%d %H:%M:%S"
TIME_FORMAT_DATE = "%Y-%m-%d"
TIME_FORMAT_LOG = "%Y%m%d_%H%M%S"

# Environment Variables
ENV_PREFIX = "CGH_"
ENV_DEBUG = f"{ENV_PREFIX}DEBUG"
ENV_DATABASE_URL = f"{ENV_PREFIX}DATABASE_URL"
ENV_REDIS_URL = f"{ENV_PREFIX}REDIS_URL"
ENV_SECRET_KEY = f"{ENV_PREFIX}SECRET_KEY"
ENV_GITHUB_TOKEN = f"{ENV_PREFIX}GITHUB_TOKEN"
ENV_LOG_LEVEL = f"{ENV_PREFIX}LOG_LEVEL"

# Feature Flags
FEATURE_AI_ANALYSIS = "ai_analysis"
FEATURE_GITHUB_INTEGRATION = "github_integration"
FEATURE_CONTAINER_SUPPORT = "container_support"
FEATURE_REAL_TIME_UPDATES = "real_time_updates"
FEATURE_ADVANCED_METRICS = "advanced_metrics"

# Metric Names
METRIC_API_REQUEST_COUNT = "api_request_count"
METRIC_API_REQUEST_DURATION = "api_request_duration"
METRIC_API_ERROR_COUNT = "api_error_count"
METRIC_CONTAINER_COUNT = "container_count"
METRIC_ANALYSIS_DURATION = "analysis_duration"
METRIC_CACHE_HIT_RATE = "cache_hit_rate"

# Queue Names
QUEUE_ANALYSIS = "analysis"
QUEUE_GITHUB_WEBHOOK = "github_webhook"
QUEUE_TEST_EXECUTION = "test_execution"
QUEUE_NOTIFICATION = "notification"
QUEUE_CLEANUP = "cleanup"

# Default Values
DEFAULT_BRANCH = "main"
DEFAULT_LANGUAGE = "python"
DEFAULT_ENCODING = "utf-8"
DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 3

# Validation Limits
MAX_NAME_LENGTH = 255
MAX_DESCRIPTION_LENGTH = 1000
MAX_URL_LENGTH = 2000
MAX_PATH_LENGTH = 4096
MAX_QUERY_LENGTH = 10000
MAX_ARRAY_LENGTH = 1000

# Color Codes (for terminal output)
COLOR_RESET = "\033[0m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_MAGENTA = "\033[95m"
COLOR_CYAN = "\033[96m"
COLOR_WHITE = "\033[97m"

# ASCII Art (for fun terminal output)
ASCII_LOGO = r"""
 ____          _        ____                 _
/ ___|___   __| | ___  / ___|_ __ __ _ _ __ | |__
| |   / _ \ / _` |/ _ \| |  _| '__/ _` | '_ \| '_ \
| |__| (_) | (_| |  __/| |_| | | | (_| | |_) | | | |
\____\___/ \__,_|\___| \____|_|  \__,_| .__/|_| |_|
                                       |_|
"""

# System Thresholds
CPU_WARNING_THRESHOLD = 80.0  # percent
MEMORY_WARNING_THRESHOLD = 80.0  # percent
DISK_WARNING_THRESHOLD = 90.0  # percent
RESPONSE_TIME_WARNING = 1.0  # seconds

# Batch Processing
BATCH_INSERT_SIZE = 1000
BATCH_UPDATE_SIZE = 500
BATCH_DELETE_SIZE = 100
BATCH_PROCESSING_DELAY = 0.1  # seconds between batches

# Complexity Thresholds
COMPLEXITY_LOW = 5
COMPLEXITY_MEDIUM = 10
COMPLEXITY_HIGH = 20
COMPLEXITY_VERY_HIGH = 30

# Code Quality Grades
GRADE_A = "A"  # Excellent
GRADE_B = "B"  # Good
GRADE_C = "C"  # Satisfactory
GRADE_D = "D"  # Needs Improvement
GRADE_F = "F"  # Poor

GRADE_THRESHOLDS = {
    GRADE_A: 90,
    GRADE_B: 80,
    GRADE_C: 70,
    GRADE_D: 60,
    GRADE_F: 0,
}

# Common Null/Empty Values to Check
NULL_VALUES = {"null", "none", "nil", "undefined", "na", "n/a", ""}
EMPTY_VALUES = {"", " ", "\t", "\n", "\r", "\r\n"}

# API Versioning
API_VERSION_V1 = "v1"
API_VERSION_V2 = "v2"
CURRENT_API_VERSION = API_VERSION_V2
SUPPORTED_API_VERSIONS = {API_VERSION_V1, API_VERSION_V2}

# Content Types
CONTENT_TYPE_JSON = "application/json"
CONTENT_TYPE_FORM = "application/x-www-form-urlencoded"
CONTENT_TYPE_MULTIPART = "multipart/form-data"
CONTENT_TYPE_TEXT = "text/plain"

# Date/Time Constants
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400
SECONDS_PER_WEEK = 604800

# Magic Numbers (document why these values)
MAX_RECURSION_DEPTH = 100  # Prevent infinite recursion in graph traversal
MAX_RETRY_EXPONENTIAL_BACKOFF = 64  # 2^6, about 1 minute max wait
MIN_PASSWORD_LENGTH = 8  # Security requirement
MAX_LOGIN_ATTEMPTS = 5  # Before lockout
LOCKOUT_DURATION = 900  # 15 minutes in seconds

# Graph Relationship Types
REL_IMPORTS = "IMPORTS"
REL_CALLS = "CALLS"
REL_INHERITS = "INHERITS"
REL_IMPLEMENTS = "IMPLEMENTS"
REL_USES = "USES"
REL_DEPENDS_ON = "DEPENDS_ON"
REL_CONTAINS = "CONTAINS"
REL_REFERENCES = "REFERENCES"

# Node Types
NODE_FILE = "File"
NODE_CLASS = "Class"
NODE_FUNCTION = "Function"
NODE_METHOD = "Method"
NODE_MODULE = "Module"
NODE_PACKAGE = "Package"
NODE_VARIABLE = "Variable"
NODE_IMPORT = "Import"

# Analysis Status
STATUS_PENDING = "pending"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"
STATUS_TIMEOUT = "timeout"

# Priority Levels
PRIORITY_LOW = 1
PRIORITY_MEDIUM = 2
PRIORITY_HIGH = 3
PRIORITY_CRITICAL = 4

PRIORITY_NAMES = {
    PRIORITY_LOW: "low",
    PRIORITY_MEDIUM: "medium",
    PRIORITY_HIGH: "high",
    PRIORITY_CRITICAL: "critical",
}

# Severity Levels
SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"
SEVERITY_CRITICAL = "critical"

# Common Regex Validators as compiled patterns (for performance)

COMPILED_EMAIL = re.compile(REGEX_EMAIL)
COMPILED_URL = re.compile(REGEX_URL)
COMPILED_GITHUB_REPO = re.compile(REGEX_GITHUB_REPO)
COMPILED_SEMVER = re.compile(REGEX_SEMVER)
COMPILED_UUID = re.compile(REGEX_UUID, re.IGNORECASE)
COMPILED_CONTAINER_NAME = re.compile(REGEX_CONTAINER_NAME)

# Frozen sets for performance (immutable and faster lookup)
FROZEN_NULL_VALUES = frozenset(NULL_VALUES)
FROZEN_EMPTY_VALUES = frozenset(EMPTY_VALUES)
FROZEN_IGNORE_PATTERNS = frozenset(IGNORE_PATTERNS)
FROZEN_SUPPORTED_LANGUAGES = frozenset(SUPPORTED_LANGUAGES)

# Type Aliases for clarity
FileExtensions = set[str]
LanguageMap = dict[str, FileExtensions]
Headers = dict[str, str]
Seconds = float
Bytes = int
Percent = float

# Export groups for easier imports
__all__ = [
    # HTTP
    "HTTP_TIMEOUT_DEFAULT",
    "HTTP_TIMEOUT_LONG",
    "HTTP_TIMEOUT_SHORT",
    "HTTP_RETRY_COUNT",
    "HTTP_RETRY_BACKOFF",
    "HTTP_RETRY_STATUS_CODES",
    "HEADERS_JSON",
    "HEADERS_ACCEPT_JSON",
    "HEADERS_GITHUB",
    # Pagination
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "MIN_PAGE_SIZE",
    "DEFAULT_PAGE_NUMBER",
    # Cache
    "CACHE_TTL_SHORT",
    "CACHE_TTL_MEDIUM",
    "CACHE_TTL_LONG",
    "CACHE_TTL_VERY_LONG",
    "CACHE_KEY_PREFIX",
    # File Operations
    "MAX_FILE_SIZE",
    "CHUNK_SIZE",
    "IGNORE_PATTERNS",
    "LANGUAGE_EXTENSIONS",
    "SUPPORTED_LANGUAGES",
    # Database
    "DB_POOL_SIZE",
    "DB_MAX_OVERFLOW",
    "DB_POOL_TIMEOUT",
    "DB_TRANSACTION_TIMEOUT",
    # Container
    "CONTAINER_BASE_PORT",
    "CONTAINER_HEALTH_CHECK_INTERVAL",
    "CONTAINER_HEALTH_CHECK_TIMEOUT",
    "CONTAINER_NAME_PREFIX",
    # Quality
    "MAX_FUNCTION_LENGTH",
    "MAX_FILE_LENGTH",
    "MAX_CYCLOMATIC_COMPLEXITY",
    "MAX_LINE_LENGTH",
    # Security
    "MAX_REQUEST_SIZE",
    "ALLOWED_UPLOAD_EXTENSIONS",
    # Common Values
    "NULL_VALUES",
    "FROZEN_NULL_VALUES",
    "DEFAULT_BRANCH",
    "DEFAULT_LANGUAGE",
    "DEFAULT_ENCODING",
    # Status and Priority
    "STATUS_PENDING",
    "STATUS_IN_PROGRESS",
    "STATUS_COMPLETED",
    "STATUS_FAILED",
    "PRIORITY_NAMES",
    "SEVERITY_INFO",
    "SEVERITY_WARNING",
    "SEVERITY_ERROR",
    "SEVERITY_CRITICAL",
    # Compiled Regex
    "COMPILED_EMAIL",
    "COMPILED_URL",
    "COMPILED_GITHUB_REPO",
    "COMPILED_UUID",
]
