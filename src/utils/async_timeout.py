"""
Async timeout utilities for handling long-running operations.

This module provides comprehensive timeout management for async operations,
including decorators, context managers, and task management utilities.
It helps prevent operations from hanging indefinitely and provides
proactive timeout handling with detailed error reporting.

Key Components:
    - AsyncTimeoutError: Custom HTTP timeout exception for API operations
    - run_with_timeout: Utility function to run coroutines with timeout
    - with_timeout: Decorator for adding timeout to async functions
    - AsyncTaskManager: Manager for handling background async tasks

Timeout Features:
    - Automatic cleanup of timed-out operations
    - Detailed error messages with timeout duration
    - Background task management with status tracking
    - Task cancellation and result retrieval
    - HTTP-compatible timeout exceptions

Usage:
    >>> @with_timeout(30.0, "Analysis timed out")
    >>> async def analyze_code(repo_path):
    >>>     # Long-running analysis code
    >>>     pass
    >>>
    >>> # Or use directly
    >>> result = await run_with_timeout(some_coro(), 60.0)
    >>>
    >>> # Task management
    >>> task_id = task_manager.submit_task("analysis", analyze_code(path))
    >>> status = task_manager.get_task_status(task_id)
"""

from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AsyncTimeoutError(HTTPException):
    """Custom timeout exception for API operations.

    This exception is raised when async operations exceed their configured
    timeout duration. It extends HTTPException to provide HTTP-compatible
    error responses with 408 Request Timeout status code.

    Attributes:
        status_code: HTTP status code (408 Request Timeout)
        detail: Error message including timeout duration
        timeout_seconds: The timeout duration that was exceeded
    """

    def __init__(self, detail: str, timeout_seconds: float):
        """
        Initialize a timeout error with context information.

        Args:
            detail: Human-readable error detail message describing the operation
            timeout_seconds: The timeout duration in seconds that was exceeded

        Example:
            >>> raise AsyncTimeoutError("Database query timed out", 30.0)
            # Results in HTTP 408 with message: "Database query timed out (timeout: 30.0s)"
        """
        super().__init__(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail=f"{detail} (timeout: {timeout_seconds}s)",
        )
        self.timeout_seconds = timeout_seconds


async def run_with_timeout[T](
    coro: Awaitable[T],
    timeout_seconds: float,
    timeout_message: str = "Operation timed out",
) -> T:
    """
    Run an async coroutine with a timeout.

    Wraps any awaitable with a timeout mechanism, automatically canceling
    the operation if it exceeds the specified duration. This prevents
    operations from hanging indefinitely and provides predictable behavior.

    Args:
        coro: The coroutine (awaitable) to run with timeout protection
        timeout_seconds: Maximum time to wait in seconds (can be fractional)
        timeout_message: Custom error message if timeout occurs

    Returns:
        The result of the coroutine if completed within timeout

    Raises:
        AsyncTimeoutError: If the operation times out, with HTTP 408 status
        Any other exception: Propagated from the original coroutine

    Example:
        >>> result = await run_with_timeout(
        ...     expensive_operation(),
        ...     30.0,
        ...     "Code analysis timed out"
        ... )

    Note:
        The timeout is enforced using asyncio.wait_for, which will
        cancel the underlying coroutine if it doesn't complete in time.
        This ensures proper cleanup of resources.
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except TimeoutError:
        logger.warning(f"Operation timed out after {timeout_seconds}s: {timeout_message}")
        raise AsyncTimeoutError(timeout_message, timeout_seconds)


def with_timeout(timeout_seconds: float, timeout_message: str | None = None):
    """
    Decorator to add timeout to async functions.

    This decorator wraps async functions with automatic timeout handling,
    preventing them from running indefinitely. It preserves the original
    function signature and docstring while adding timeout protection.

    Args:
        timeout_seconds: Maximum time to wait in seconds (can be fractional)
        timeout_message: Optional custom timeout message (defaults to function name)

    Returns:
        Decorator function that wraps async functions with timeout protection

    Usage:
        >>> @with_timeout(30.0, "Graph initialization timed out")
        >>> async def initialize_graph(repo_path: str) -> GraphResult:
        >>>     # Long-running graph initialization
        >>>     return await build_graph(repo_path)
        >>>
        >>> # Function automatically times out after 30 seconds
        >>> result = await initialize_graph("/path/to/repo")

    Note:
        The decorator preserves the original function's type hints and
        metadata using functools.wraps. The timeout is applied to each
        individual function call, not globally.
    """

    def decorator(
        func: Callable[..., Awaitable[T]],
    ) -> Callable[..., Awaitable[T]]:
        func_name = getattr(func, "__name__", repr(func))

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            message = timeout_message or f"{func_name} timed out"
            return await run_with_timeout(func(*args, **kwargs), timeout_seconds, message)

        return wrapper

    return decorator


class AsyncTaskManager:
    """Manager for handling long-running async tasks.

    This class provides comprehensive task management capabilities for
    async operations, including task submission, status tracking, result
    retrieval, and cancellation. It's designed for scenarios where you
    need to run async operations in the background and check their
    status later.

    Features:
        - Background task execution with unique task IDs
        - Status tracking (running, completed, failed, not_found)
        - Result storage and retrieval
        - Error handling and logging
        - Task cancellation support
        - Automatic cleanup of completed tasks

    Attributes:
        tasks: Dictionary mapping task IDs to active asyncio.Task objects
        results: Dictionary storing results of completed tasks
        errors: Dictionary storing error messages from failed tasks

    Usage:
        >>> manager = AsyncTaskManager()
        >>> task_id = manager.submit_task("analysis", analyze_code(path))
        >>> # Check status later
        >>> status = manager.get_task_status(task_id)
        >>> if status["status"] == "completed":
        >>>     result = status["result"]
    """

    def __init__(self):
        """
        Initialize the task manager with empty task tracking dictionaries.

        Creates empty dictionaries for tracking active tasks, completed
        results, and error messages. All task state is maintained in
        memory and will be lost when the manager is destroyed.
        """
        self.tasks: dict[str, asyncio.Task] = {}
        self.results: dict[str, Any] = {}
        self.errors: dict[str, str] = {}

    def submit_task(self, task_id: str, coro: Awaitable[Any]) -> str:
        """
        Submit a task for background execution.

        Creates a new asyncio task for the given coroutine and tracks it
        under the specified task ID. The task runs in the background and
        its result or error will be stored for later retrieval.

        Args:
            task_id: Unique identifier for the task (must not already exist)
            coro: The coroutine to execute in the background

        Returns:
            The task ID (same as input, for convenience)

        Raises:
            ValueError: If a task with the given ID already exists

        Example:
            >>> manager = AsyncTaskManager()
            >>> task_id = manager.submit_task("scan_123", scan_repository(repo_path))
            >>> # Task is now running in background
            >>> print(f"Submitted task: {task_id}")
        """
        if task_id in self.tasks:
            raise ValueError(f"Task {task_id} already exists")

        task = asyncio.create_task(self._run_task(task_id, coro))
        self.tasks[task_id] = task
        return task_id

    async def _run_task(self, task_id: str, coro: Awaitable[Any]) -> None:
        """
        Run a task and store its result or error.

        Internal method that executes the task coroutine and handles
        both successful completion and error cases. Results are stored
        in the appropriate dictionaries and the task is cleaned up
        from the active tasks list.

        Args:
            task_id: Unique identifier for the task being executed
            coro: The coroutine to execute

        Note:
            This method is called internally by submit_task() and should
            not be called directly. It ensures proper error handling,
            logging, and cleanup regardless of task outcome.
        """
        try:
            result = await coro
            self.results[task_id] = result
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            self.errors[task_id] = str(e)
        finally:
            # Clean up completed task
            if task_id in self.tasks:
                del self.tasks[task_id]

    def get_task_status(self, task_id: str) -> dict[str, Any]:
        """
        Get the status of a task.

        Retrieves the current status of a task, including its result
        if completed or error information if failed. This method can
        be called repeatedly to poll task progress.

        Args:
            task_id: Unique identifier for the task to check

        Returns:
            Dict with status information containing:
            - "status": One of "running", "completed", "failed", "not_found"
            - "task_id": The task identifier
            - "result": Task result (only if status is "completed")
            - "error": Error message (only if status is "failed")

        Example:
            >>> status = manager.get_task_status("scan_123")
            >>> if status["status"] == "completed":
            >>>     print(f"Task completed: {status['result']}")
            >>> elif status["status"] == "failed":
            >>>     print(f"Task failed: {status['error']}")
            >>> elif status["status"] == "running":
            >>>     print("Task is still running...")
        """
        if task_id in self.tasks:
            return {"status": "running", "task_id": task_id}
        elif task_id in self.results:
            return {
                "status": "completed",
                "task_id": task_id,
                "result": self.results[task_id],
            }
        elif task_id in self.errors:
            return {
                "status": "failed",
                "task_id": task_id,
                "error": self.errors[task_id],
            }
        else:
            return {"status": "not_found", "task_id": task_id}

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running task.

        Attempts to cancel a task that is currently running. Only active
        tasks can be cancelled; completed or failed tasks cannot be cancelled.
        The task will be removed from the active tasks list.

        Args:
            task_id: Unique identifier for the task to cancel

        Returns:
            True if task was found and cancelled, False if task was not found
            or was not in a cancellable state

        Example:
            >>> success = manager.cancel_task("long_running_task")
            >>> if success:
            >>>     print("Task cancelled successfully")
            >>> else:
            >>>     print("Task not found or already completed")

        Note:
            Cancelled tasks will not appear in results or errors dictionaries.
            The task coroutine will receive a CancelledError exception.
        """
        if task_id in self.tasks:
            self.tasks[task_id].cancel()
            del self.tasks[task_id]
            return True
        return False


# Global task manager instance
task_manager = AsyncTaskManager()
"""Global instance of AsyncTaskManager for application-wide task management.

This singleton instance can be used throughout the application to manage
long-running async tasks. It provides a centralized way to submit, track,
and cancel background operations.

Example:
    >>> from utils.async_timeout import task_manager
    >>> task_id = task_manager.submit_task("analysis", analyze_code(path))
    >>> # Later, check status
    >>> status = task_manager.get_task_status(task_id)
"""
