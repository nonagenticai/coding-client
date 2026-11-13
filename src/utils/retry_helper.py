"""
Retry helper utilities for handling transient failures with backoff.

This module provides reusable retry logic using tenacity for:
- Docker API calls (@retry_docker)
- Database operations (@retry_database)
- HTTP/network calls (@retry_network)

All decorators support both sync and async functions with configurable
max_retries, backoff strategies, and exception filtering.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import socket
import sqlite3
from collections.abc import Awaitable, Callable, Sequence
from functools import wraps
from typing import Any, ParamSpec, TypeVar, overload

from tenacity import (
    AsyncRetrying,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_fixed,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")


# =============================================================================
# Exception Categories for Retry Logic
# =============================================================================

# Docker-related exceptions that are worth retrying
DOCKER_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
    socket.error,
)

# Database-related exceptions that are worth retrying
DATABASE_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    sqlite3.OperationalError,
    OSError,
    TimeoutError,
)

# Network-related exceptions that are worth retrying
NETWORK_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    ConnectionError,
    ConnectionRefusedError,
    ConnectionResetError,
    TimeoutError,
    OSError,
    socket.error,
    socket.timeout,
)


# =============================================================================
# Logging Callbacks
# =============================================================================


def _log_retry_attempt(retry_state: Any, operation_type: str = "operation") -> None:
    """Log retry attempt with context."""
    fn_name = getattr(retry_state.fn, "__name__", "unknown")
    attempt = retry_state.attempt_number
    exception = retry_state.outcome.exception() if retry_state.outcome else None

    if exception:
        logger.warning(
            f"[RETRY] {operation_type} '{fn_name}' failed (attempt {attempt}): {type(exception).__name__}: {exception}"
        )
    else:
        logger.warning(f"[RETRY] {operation_type} '{fn_name}' retrying (attempt {attempt})")


def _log_docker_retry(retry_state: Any) -> None:
    """Log Docker API retry attempt."""
    _log_retry_attempt(retry_state, "Docker API")


def _log_database_retry(retry_state: Any) -> None:
    """Log database retry attempt."""
    _log_retry_attempt(retry_state, "Database")


def _log_network_retry(retry_state: Any) -> None:
    """Log network retry attempt."""
    _log_retry_attempt(retry_state, "Network")


# =============================================================================
# Retry Decorators Using Tenacity
# =============================================================================


def retry_docker(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    multiplier: float = 2.0,
    reraise: bool = True,
) -> Callable[..., Any]:
    """
    Decorator for retrying Docker API calls with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        min_wait: Minimum wait time between retries in seconds (default: 1.0)
        max_wait: Maximum wait time between retries in seconds (default: 10.0)
        multiplier: Multiplier for exponential backoff (default: 2.0)
        reraise: Whether to reraise the last exception (default: True)

    Returns:
        Decorated function with retry logic

    Example:
        @retry_docker(max_attempts=5)
        async def pull_image(image_name: str) -> None:
            ...
    """

    @overload
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]: ...
    @overload
    def decorator(func: Callable[P, R]) -> Callable[P, R]: ...
    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=multiplier, min=min_wait, max=max_wait),
                retry=retry_if_exception_type(DOCKER_RETRYABLE_EXCEPTIONS),
                before_sleep=_log_docker_retry,
                reraise=reraise,
            ):
                with attempt:
                    return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            for attempt in Retrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=multiplier, min=min_wait, max=max_wait),
                retry=retry_if_exception_type(DOCKER_RETRYABLE_EXCEPTIONS),
                before_sleep=_log_docker_retry,
                reraise=reraise,
            ):
                with attempt:
                    return func(*args, **kwargs)

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def retry_database(
    max_attempts: int = 3,
    min_wait: float = 0.5,
    max_wait: float = 5.0,
    multiplier: float = 2.0,
    reraise: bool = True,
) -> Callable[..., Any]:
    """
    Decorator for retrying database operations with exponential backoff.

    Handles SQLite operational errors, lock contention, and I/O issues.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        min_wait: Minimum wait time between retries in seconds (default: 0.5)
        max_wait: Maximum wait time between retries in seconds (default: 5.0)
        multiplier: Multiplier for exponential backoff (default: 2.0)
        reraise: Whether to reraise the last exception (default: True)

    Returns:
        Decorated function with retry logic

    Example:
        @retry_database(max_attempts=5)
        async def execute_query(sql: str) -> list:
            ...
    """

    @overload
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]: ...
    @overload
    def decorator(func: Callable[P, R]) -> Callable[P, R]: ...
    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=multiplier, min=min_wait, max=max_wait),
                retry=retry_if_exception_type(DATABASE_RETRYABLE_EXCEPTIONS),
                before_sleep=_log_database_retry,
                reraise=reraise,
            ):
                with attempt:
                    return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            for attempt in Retrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=multiplier, min=min_wait, max=max_wait),
                retry=retry_if_exception_type(DATABASE_RETRYABLE_EXCEPTIONS),
                before_sleep=_log_database_retry,
                reraise=reraise,
            ):
                with attempt:
                    return func(*args, **kwargs)

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def retry_network(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 30.0,
    multiplier: float = 2.0,
    reraise: bool = True,
    additional_exceptions: Sequence[type[Exception]] | None = None,
) -> Callable[..., Any]:
    """
    Decorator for retrying HTTP/network calls with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        min_wait: Minimum wait time between retries in seconds (default: 1.0)
        max_wait: Maximum wait time between retries in seconds (default: 30.0)
        multiplier: Multiplier for exponential backoff (default: 2.0)
        reraise: Whether to reraise the last exception (default: True)
        additional_exceptions: Additional exception types to retry on

    Returns:
        Decorated function with retry logic

    Example:
        @retry_network(max_attempts=5, additional_exceptions=[RequestException])
        async def fetch_data(url: str) -> dict:
            ...
    """
    exceptions_to_retry = NETWORK_RETRYABLE_EXCEPTIONS
    if additional_exceptions:
        exceptions_to_retry = tuple(list(exceptions_to_retry) + list(additional_exceptions))

    @overload
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]: ...
    @overload
    def decorator(func: Callable[P, R]) -> Callable[P, R]: ...
    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=multiplier, min=min_wait, max=max_wait),
                retry=retry_if_exception_type(exceptions_to_retry),
                before_sleep=_log_network_retry,
                reraise=reraise,
            ):
                with attempt:
                    return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            for attempt in Retrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=multiplier, min=min_wait, max=max_wait),
                retry=retry_if_exception_type(exceptions_to_retry),
                before_sleep=_log_network_retry,
                reraise=reraise,
            ):
                with attempt:
                    return func(*args, **kwargs)

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def retry_with_config(
    max_attempts: int = 3,
    wait_strategy: str = "exponential",
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    multiplier: float = 2.0,
    fixed_wait: float = 1.0,
    exceptions: Sequence[type[Exception]] | None = None,
    operation_name: str = "operation",
    reraise: bool = True,
) -> Callable[..., Any]:
    """
    Generic retry decorator with configurable strategy.

    Args:
        max_attempts: Maximum number of retry attempts
        wait_strategy: "exponential" or "fixed"
        min_wait: Minimum wait for exponential backoff
        max_wait: Maximum wait time
        multiplier: Multiplier for exponential backoff
        fixed_wait: Wait time for fixed strategy
        exceptions: Tuple of exception types to retry on
        operation_name: Name for logging purposes
        reraise: Whether to reraise the last exception

    Returns:
        Decorated function with retry logic
    """
    if exceptions is None:
        exceptions = (Exception,)
    exceptions_tuple = tuple(exceptions)

    if wait_strategy == "fixed":
        wait_fn = wait_fixed(fixed_wait)
    else:
        wait_fn = wait_exponential(multiplier=multiplier, min=min_wait, max=max_wait)

    def log_retry(retry_state: Any) -> None:
        _log_retry_attempt(retry_state, operation_name)

    @overload
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]: ...
    @overload
    def decorator(func: Callable[P, R]) -> Callable[P, R]: ...
    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_fn,
                retry=retry_if_exception_type(exceptions_tuple),
                before_sleep=log_retry,
                reraise=reraise,
            ):
                with attempt:
                    return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            for attempt in Retrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_fn,
                retry=retry_if_exception_type(exceptions_tuple),
                before_sleep=log_retry,
                reraise=reraise,
            ):
                with attempt:
                    return func(*args, **kwargs)

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# =============================================================================
# Legacy Support - RetryConfig and RetryHelper classes
# =============================================================================


class RetryConfig:
    """Configuration for retry behavior (legacy support)."""

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0,
        max_delay: float = 60.0,
        retryable_exceptions: Sequence[type[Exception]] = (Exception,),
        retry_on_result: Callable[[Any], bool] | None = None,
    ):
        """
        Initialize retry configuration.

        Args:
            max_attempts: Maximum number of attempts (including initial)
            initial_delay: Initial delay between retries in seconds
            backoff_factor: Multiplier for delay after each attempt
            max_delay: Maximum delay between retries
            retryable_exceptions: Tuple of exception types to retry on
            retry_on_result: Optional function to check if result should trigger retry
        """
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay
        self.retryable_exceptions = tuple(retryable_exceptions)
        self.retry_on_result = retry_on_result


class RetryHelper:
    """Helper class for retry operations with exponential backoff (legacy support)."""

    @staticmethod
    def calculate_delay(
        attempt: int,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0,
        max_delay: float = 60.0,
    ) -> float:
        """
        Calculate delay for a given attempt using exponential backoff.

        Args:
            attempt: Current attempt number (0-indexed)
            initial_delay: Initial delay in seconds
            backoff_factor: Multiplier for each subsequent attempt
            max_delay: Maximum delay cap

        Returns:
            Delay in seconds for the current attempt
        """
        delay = initial_delay * (backoff_factor**attempt)
        return min(delay, max_delay)

    @staticmethod
    async def retry_async(
        func: Callable[..., Any],
        *args: Any,
        config: RetryConfig | None = None,
        **kwargs: Any,
    ) -> Any:
        """
        Execute an async function with retry logic.

        Args:
            func: Async function to execute
            *args: Positional arguments to pass to func
            config: Retry configuration (uses defaults if None)
            **kwargs: Keyword arguments to pass to func

        Returns:
            Result from the function

        Raises:
            Last exception if all retries exhausted
        """
        if config is None:
            config = RetryConfig()

        last_exception: BaseException | None = None

        for attempt in range(config.max_attempts):
            try:
                result = await func(*args, **kwargs)

                # Check if result should trigger retry
                if config.retry_on_result and config.retry_on_result(result):
                    if attempt < config.max_attempts - 1:
                        delay = RetryHelper.calculate_delay(
                            attempt,
                            config.initial_delay,
                            config.backoff_factor,
                            config.max_delay,
                        )
                        logger.debug(
                            f"Retry triggered by result check, attempt {attempt + 1}/{config.max_attempts}, "
                            f"waiting {delay:.2f}s"
                        )
                        await asyncio.sleep(delay)
                        continue

                return result

            except config.retryable_exceptions as e:
                last_exception = e
                if attempt < config.max_attempts - 1:
                    delay = RetryHelper.calculate_delay(
                        attempt,
                        config.initial_delay,
                        config.backoff_factor,
                        config.max_delay,
                    )
                    logger.warning(
                        f"Attempt {attempt + 1}/{config.max_attempts} failed: {e}. Retrying in {delay:.2f}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All {config.max_attempts} attempts failed. Last error: {e}")

        if last_exception:
            raise last_exception
        raise RuntimeError("Retry exhausted without result or exception")

    @staticmethod
    def retry_sync(
        func: Callable[..., T],
        *args: Any,
        config: RetryConfig | None = None,
        **kwargs: Any,
    ) -> T:
        """
        Execute a sync function with retry logic.

        Args:
            func: Sync function to execute
            *args: Positional arguments to pass to func
            config: Retry configuration (uses defaults if None)
            **kwargs: Keyword arguments to pass to func

        Returns:
            Result from the function

        Raises:
            Last exception if all retries exhausted
        """
        import time

        if config is None:
            config = RetryConfig()

        last_exception: BaseException | None = None

        for attempt in range(config.max_attempts):
            try:
                result = func(*args, **kwargs)

                # Check if result should trigger retry
                if config.retry_on_result and config.retry_on_result(result):
                    if attempt < config.max_attempts - 1:
                        delay = RetryHelper.calculate_delay(
                            attempt,
                            config.initial_delay,
                            config.backoff_factor,
                            config.max_delay,
                        )
                        logger.debug(
                            f"Retry triggered by result check, attempt {attempt + 1}/{config.max_attempts}, "
                            f"waiting {delay:.2f}s"
                        )
                        time.sleep(delay)
                        continue

                return result

            except config.retryable_exceptions as e:
                last_exception = e
                if attempt < config.max_attempts - 1:
                    delay = RetryHelper.calculate_delay(
                        attempt,
                        config.initial_delay,
                        config.backoff_factor,
                        config.max_delay,
                    )
                    logger.warning(
                        f"Attempt {attempt + 1}/{config.max_attempts} failed: {e}. Retrying in {delay:.2f}s"
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"All {config.max_attempts} attempts failed. Last error: {e}")

        if last_exception:
            raise last_exception
        raise RuntimeError("Retry exhausted without result or exception")

    @staticmethod
    async def poll_until(
        check_func: Callable[..., Any],
        *args: Any,
        condition: Callable[[Any], bool] | None = None,
        max_attempts: int = 30,
        poll_interval: float = 2.0,
        timeout: float | None = None,
        description: str = "condition",
        **kwargs: Any,
    ) -> Any:
        """
        Poll a function until a condition is met or timeout occurs.

        Args:
            check_func: Async function to check (can be sync, will be wrapped)
            *args: Positional arguments for check_func
            condition: Function to evaluate result (default: truthy check)
            max_attempts: Maximum poll attempts
            poll_interval: Seconds between polls
            timeout: Optional total timeout in seconds
            description: Description for logging
            **kwargs: Keyword arguments for check_func

        Returns:
            Result that satisfied the condition

        Raises:
            TimeoutError: If condition not met within limits
        """
        if condition is None:
            condition = bool

        start_time = asyncio.get_event_loop().time()

        for attempt in range(max_attempts):
            # Check timeout
            if timeout is not None:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= timeout:
                    raise TimeoutError(f"Polling for {description} timed out after {elapsed:.1f}s")

            try:
                # Handle both sync and async functions
                if inspect.iscoroutinefunction(check_func):
                    result = await check_func(*args, **kwargs)
                else:
                    result = check_func(*args, **kwargs)

                if condition(result):
                    logger.debug(f"Condition '{description}' met after {attempt + 1} attempts")
                    return result

            except (
                Exception
            ) as e:  # Intentionally broad: check_func is an arbitrary caller-supplied callback
                logger.debug(
                    f"Poll attempt {attempt + 1}/{max_attempts} for '{description}' raised: {e}"
                )

            if attempt < max_attempts - 1:
                await asyncio.sleep(poll_interval)

        raise TimeoutError(f"Condition '{description}' not met after {max_attempts} attempts")


def with_retry(
    config: RetryConfig | None = None,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: Sequence[type[Exception]] = (Exception,),
) -> Callable[..., Any]:
    """
    Legacy decorator for adding retry logic to async functions.

    Args:
        config: RetryConfig instance (overrides other params if provided)
        max_attempts: Maximum attempts if config not provided
        initial_delay: Initial delay if config not provided
        backoff_factor: Backoff factor if config not provided
        retryable_exceptions: Exceptions to retry on if config not provided

    Returns:
        Decorated function with retry logic
    """
    if config is None:
        config = RetryConfig(
            max_attempts=max_attempts,
            initial_delay=initial_delay,
            backoff_factor=backoff_factor,
            retryable_exceptions=retryable_exceptions,
        )

    @overload
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]: ...
    @overload
    def decorator(func: Callable[P, R]) -> Callable[P, R]: ...
    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            return await RetryHelper.retry_async(func, *args, config=config, **kwargs)

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            return RetryHelper.retry_sync(func, *args, config=config, **kwargs)

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Primary decorators (recommended)
    "retry_docker",
    "retry_database",
    "retry_network",
    "retry_with_config",
    # Exception categories
    "DOCKER_RETRYABLE_EXCEPTIONS",
    "DATABASE_RETRYABLE_EXCEPTIONS",
    "NETWORK_RETRYABLE_EXCEPTIONS",
    # Legacy support
    "RetryConfig",
    "RetryHelper",
    "with_retry",
]
