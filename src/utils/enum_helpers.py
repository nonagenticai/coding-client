"""
Enum helper utilities for safe value extraction.

This module provides utilities to reduce cyclomatic complexity when
extracting values from enums or enum-like objects across the codebase.
"""

from enum import Enum
from typing import Any, TypeVar, cast

T = TypeVar("T")


def safe_get_enum_value(
    obj: Any,
    attr_name: str,
    default: str = "unknown",
) -> str:
    """
    Safely extract enum value from an object attribute.

    Handles cases where:
    - The attribute doesn't exist
    - The attribute is an Enum (extracts .value)
    - The attribute is already a string
    - The attribute is None

    Args:
        obj: Object to extract attribute from
        attr_name: Name of the attribute to extract
        default: Default value if attribute not found or None

    Returns:
        String value of the attribute

    Example:
        # Instead of:
        # getattr(insight, "severity", "info").value if hasattr(...) else str(...)

        # Use:
        safe_get_enum_value(insight, "severity", "info")
    """
    value = getattr(obj, attr_name, None)

    if value is None:
        return default

    if isinstance(value, Enum):
        return str(value.value)

    if hasattr(value, "value"):
        return str(value.value)

    return str(value)


def safe_get_nested_enum(
    obj: Any,
    *attr_path: str,
    default: str = "unknown",
) -> str:
    """
    Safely extract enum value from a nested attribute path.

    Args:
        obj: Root object to start from
        *attr_path: Sequence of attribute names to traverse
        default: Default value if path doesn't exist

    Returns:
        String value of the final attribute

    Example:
        # Instead of deeply nested getattr chains:
        safe_get_nested_enum(result, "analysis", "severity", default="low")
    """
    current = obj

    for attr in attr_path:
        current = getattr(current, attr, None)
        if current is None:
            return default

    if isinstance(current, Enum):
        return str(current.value)

    if hasattr(current, "value"):
        return str(current.value)

    return str(current)


def enum_to_str(value: Enum | str | None, default: str = "unknown") -> str:
    """
    Convert an enum or string to string representation.

    Args:
        value: Enum instance, string, or None
        default: Default value if None

    Returns:
        String representation
    """
    if value is None:
        return default

    if isinstance(value, Enum):
        return str(value.value)

    if hasattr(value, "value"):
        return str(value.value)

    return str(value)


def safe_enum_name(value: Enum | str | None, default: str = "unknown") -> str:
    """
    Get the name of an enum (not its value).

    Args:
        value: Enum instance or string
        default: Default if None

    Returns:
        Enum name as string
    """
    if value is None:
        return default

    if isinstance(value, Enum):
        return value.name

    if hasattr(value, "name"):
        return str(value.name)

    return str(value)


def get_enum_or_default[T](
    enum_class: type,
    value: Any,
    default: T | None = None,
) -> Enum | T | None:
    """
    Safely get an enum member by value, with fallback.

    Args:
        enum_class: The enum class to look up
        value: Value to look up in the enum
        default: Default to return if not found

    Returns:
        Enum member or default

    Example:
        status = get_enum_or_default(StatusEnum, "active", StatusEnum.UNKNOWN)
    """
    if value is None:
        return default

    try:
        if isinstance(value, enum_class):
            return cast(Enum, value)
        return cast(Enum, enum_class(value))
    except (ValueError, KeyError):
        return default
