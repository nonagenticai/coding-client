"""Validation models for multi-language code validation endpoints.

This module provides language-specific validation models that ensure consistent
request/response structures across different programming languages. The models
are designed with Pydantic v2/v3 compatibility and support specialized validation
options for each supported language.

The validation system handles:
- Language-specific validation requirements (class names, project types, etc.)
- Consistent error reporting across all languages
- Type-safe request/response validation
- Proper field aliasing for API compatibility

Supported Languages:
    - Python: General-purpose validation with filename support
    - JavaScript/TypeScript: ES6+ and TypeScript validation
    - Java: Class-based validation with className parameter
    - Rust: Crate-based validation with crate type specification
    - C#: Project-based validation with framework targeting
    - Go: Package-based validation with Go module support

Example:
    ```python
    from validation_models import JavaValidationRequest, ValidationResponse

    # Create Java validation request
    request = JavaValidationRequest(
        code='public class Hello { public static void main(String[] args) { System.out.println("Hello"); } }',
        className="Hello"
    )

    # Process validation response
    response = ValidationResponse(
        validationId="val-123",
        valid=True,
        errors=[],
        output="Compilation successful"
    )
    ```
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ValidationRequest(BaseModel):
    """Base validation request model."""

    model_config = ConfigDict(
        extra="forbid",  # Reject extra fields
        str_strip_whitespace=True,  # Strip whitespace from strings
    )

    code: str = Field(..., description="Code to validate")

    @field_validator("code")
    @classmethod
    def validate_code_not_none(cls, v: str) -> str:
        """Ensure code is provided and not None."""
        if v is None:
            raise ValueError("Code field is required")
        return v


class JavaScriptValidationRequest(ValidationRequest):
    """JavaScript/TypeScript validation request."""

    filename: str | None = Field(default="test.js", description="Filename for validation")


class PythonValidationRequest(ValidationRequest):
    """Python validation request."""

    filename: str | None = Field(default="test.py", description="Filename for validation")


class JavaValidationRequest(ValidationRequest):
    """Java validation request."""

    className: str | None = Field(default="Test", description="Java class name")


class RustValidationRequest(ValidationRequest):
    """Rust validation request."""

    crateType: Literal["bin", "lib"] | None = Field(default="bin", description="Crate type")


class CSharpValidationRequest(ValidationRequest):
    """C# validation request."""

    projectType: Literal["console", "library"] | None = Field(
        default="console", description="Project type"
    )
    targetFramework: str | None = Field(default="net8.0", description="Target framework")


class GoValidationRequest(ValidationRequest):
    """Go validation request."""

    filename: str | None = Field(default="main.go", description="Filename for validation")


class ValidationResponse(BaseModel):
    """Validation response model."""

    model_config = ConfigDict(extra="forbid")

    validationId: str = Field(..., description="Unique validation ID")
    valid: bool = Field(..., description="Whether the code is valid")
    errors: list[str] = Field(default_factory=list, description="List of validation errors")
    output: str = Field(default="", description="Validation output")
    warnings: list[str] | None = Field(default=None, description="List of warnings")


class CodeValidationErrorResponse(BaseModel):
    """Validation error response model."""

    model_config = ConfigDict(extra="forbid")

    validationId: str | None = Field(default=None, description="Validation ID if available")
    valid: bool = Field(default=False, description="Always false for errors")
    error: str = Field(..., description="Error message")
    details: str | None = Field(default=None, description="Additional error details")
