"""
Security Service interface for breaking circular dependencies.

This module provides abstract interfaces for security validation operations to prevent
circular dependencies and enable dependency injection.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from models.security import (
        SecurityValidationRequest,
        SecurityValidationResult,
    )


class ISecurityService(ABC):
    """Abstract interface for security validation operations."""

    @abstractmethod
    async def validate_code_security(
        self, request: SecurityValidationRequest
    ) -> SecurityValidationResult:
        """Main security validation method with comprehensive analysis.

        Args:
            request: Security validation request containing code and configuration

        Returns:
            SecurityValidationResult with safety status, violations, and risk score
        """
        ...

    @abstractmethod
    async def generate_sandbox_config(self, language: str, security_level: str) -> dict[str, Any]:
        """Generate sandbox configuration based on language and security level.

        Args:
            language: Programming language for sandbox configuration
            security_level: Security level (low, medium, high, critical)

        Returns:
            Dictionary containing sandbox configuration
        """
        ...

    @abstractmethod
    def get_dangerous_patterns(self, language: str) -> list[dict[str, Any]]:
        """Get dangerous code patterns for a specific language.

        Args:
            language: Programming language name

        Returns:
            List of pattern dictionaries with pattern, severity, description
        """
        ...

    @abstractmethod
    def get_sandbox_config(self, language: str) -> dict[str, Any] | None:
        """Get default sandbox configuration for a language.

        Args:
            language: Programming language name

        Returns:
            Sandbox configuration dictionary or None if not configured
        """
        ...
