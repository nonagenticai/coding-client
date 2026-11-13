"""Custom exceptions for coding-client.

Provides:
- API exceptions (HTTP-based, auto-convert to error responses)
- PydanticAI exceptions (for AI analysis operations)
"""

from .api_exceptions import (
    AgentConfigurationError,
    AITimeoutError,
    AIValidationError,
    AuthenticationException,
    BaseAPIException,
    ConflictException,
    ContainerNotFoundException,
    InternalServerException,
    NotFoundException,
    PermissionException,
    ProcessingException,
    RateLimitException,
    ServiceUnavailableException,
    ValidationException,
)
from .pydantic_ai_exceptions import (
    AnalysisError,
    APIKeyError,
    LLMEmptyResponseError,
    ModelNotFoundError,
    ModelProviderError,
    PydanticAIException,
    RateLimitError,
    TokenLimitError,
    create_error_response,
)

# Avoid importing AgentConfigurationError from pydantic_ai_exceptions
# as it conflicts with the one from api_exceptions. Import directly
# from the submodule if needed:
#   from coding_client.exceptions.pydantic_ai_exceptions import AgentConfigurationError as PydanticAIAgentConfigError

__all__ = [
    # API Exceptions
    "BaseAPIException",
    "AgentConfigurationError",
    "AITimeoutError",
    "AIValidationError",
    "AuthenticationException",
    "ConflictException",
    "ContainerNotFoundException",
    "InternalServerException",
    "NotFoundException",
    "PermissionException",
    "ProcessingException",
    "RateLimitException",
    "ServiceUnavailableException",
    "ValidationException",
    # PydanticAI Exceptions
    "AnalysisError",
    "APIKeyError",
    "LLMEmptyResponseError",
    "ModelNotFoundError",
    "ModelProviderError",
    "PydanticAIException",
    "RateLimitError",
    "TokenLimitError",
    "create_error_response",
]
