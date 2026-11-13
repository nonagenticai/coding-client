"""Test executor validation models for multi-language code validation.

This module provides Pydantic models for the test executor validation endpoints,
ensuring consistent request/response structures across all supported programming
languages. The models are designed with Pydantic v2/v3 compatibility and support
validation for Python, JavaScript, TypeScript, Java, Rust, C#, and Go.

The validation system uses these models to:
- Accept code validation requests with language-specific options
- Provide consistent validation responses across different languages
- Handle errors gracefully with detailed error information
- Support language-specific features like class names, project types, etc.

Classes:
    CodeValidationRequest: Base request model for code validation with language options
    CodeValidationResponse: Standardized response with validation results
    ValidationErrorResponse: Error response model for validation failures

Functions:
    validate_code_size: Check if code size is within acceptable limits
    sanitize_error_output: Clean and truncate error messages for safe output

Example:
    ```python
    from test_executor_models import CodeValidationRequest, CodeValidationResponse

    # Create a validation request
    request = CodeValidationRequest(
        code='console.log("Hello, World!");',
        filename="test.js",
        language_version="ES2022",
        strict_mode=True
    )

    # Process validation response
    response = CodeValidationResponse(
        validation_id="val-123",
        valid=True,
        errors=[],
        warnings=["Missing semicolon"],
        output="Code is syntactically valid",
        metadata={"ast_nodes": 5}
    )
    ```
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CodeValidationRequest(BaseModel):
    """Request model for code validation endpoints."""

    model_config = ConfigDict(
        str_strip_whitespace=False,  # Preserve code formatting
        validate_default=True,
        use_enum_values=True,
    )

    code: str = Field(
        ...,
        description="Source code to validate",
        min_length=0,  # Allow empty code but require the field
        max_length=1_000_000,  # 1MB limit
    )

    filename: str | None = Field(
        default=None,
        description="Optional filename for context-aware validation",
    )

    # Language-specific options
    class_name: str | None = Field(
        default=None,
        alias="className",
        description="Class name for Java/C# validation",
    )

    project_type: str | None = Field(
        default=None,
        alias="projectType",
        description="Project type for C# validation",
    )

    language_version: str | None = Field(
        default=None,
        alias="languageVersion",
        description="Language version for validation",
    )

    strict_mode: bool | None = Field(
        default=False,
        alias="strictMode",
        description="Enable strict validation rules",
    )


class CodeValidationResponse(BaseModel):
    """Response model for code validation endpoints."""

    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)

    validation_id: str = Field(
        ..., alias="validationId", description="Unique validation request ID"
    )

    valid: bool = Field(..., description="Whether the code is syntactically valid")

    errors: list[str] = Field(default_factory=list, description="List of validation errors")

    warnings: list[str] | None = Field(default=None, description="Optional list of warnings")

    output: str = Field(default="", description="Additional validation output")

    metadata: dict[str, Any] | None = Field(default=None, description="Language-specific metadata")


class TestExecutorValidationError(BaseModel):
    """Error response model for validation failures."""

    model_config = ConfigDict(populate_by_name=True)

    validation_id: str | None = Field(
        default=None,
        alias="validationId",
        description="Validation ID if available",
    )

    error: str = Field(..., description="Error message")

    details: str | None = Field(default=None, description="Detailed error information")

    code: int | None = Field(default=None, description="Error code")


# Validation utility functions
def validate_code_size(code: str, max_size: int = 1_000_000) -> bool:
    """Validate that code size is within acceptable limits.

    Checks if the UTF-8 encoded size of the code string is within the specified
    maximum size limit. This prevents processing of excessively large code files
    that could cause memory or performance issues.

    Args:
        code (str): Source code string to validate.
        max_size (int, optional): Maximum allowed size in bytes. Defaults to 1MB (1_000_000).

    Returns:
        bool: True if code size is within limits, False otherwise.

    Example:
        ```python
        code = "def hello():\\n    print('Hello, World!')"
        if validate_code_size(code):
            # Process the code
            pass
        else:
            # Reject as too large
            raise ValueError("Code exceeds maximum size limit")
        ```
    """
    return len(code.encode("utf-8")) <= max_size


def sanitize_error_output(error: str, max_length: int = 1000) -> str:
    """Sanitize and truncate error messages for safe output.

    Removes sensitive file paths and truncates long error messages to prevent
    information leakage and ensure consistent response sizes. This function
    strips out internal container paths that might reveal system structure.

    Args:
        error (str): Raw error message to sanitize.
        max_length (int, optional): Maximum length for output. Defaults to 1000.

    Returns:
        str: Sanitized error message with sensitive paths removed and length limited.

    Example:
        ```python
        raw_error = "Error in /app/test_workspace/secret_file.py: syntax error"
        clean_error = sanitize_error_output(raw_error)
        # Returns: "Error in secret_file.py: syntax error"
        ```

    Note:
        The function specifically removes:
        - /app/test_workspace/ paths (internal container structure)
        - /tmp/ paths (temporary file locations)
        - Truncates with "..." if message exceeds max_length
    """
    if not error:
        return ""

    # Remove sensitive paths
    error = error.replace("/app/test_workspace/", "")
    error = error.replace("/tmp/", "")  # nosec B108 — sanitizes path text out of an error string; not temp-file creation

    # Truncate if too long
    if len(error) > max_length:
        error = error[: max_length - 3] + "..."

    return error
