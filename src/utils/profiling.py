"""Performance profiling utilities for measuring memory usage and execution time.

This module provides decorators and context managers for detailed performance profiling
of memory usage, CPU time, and wall clock time, with optional callback reporting
for incremental progress monitoring.
"""

from __future__ import annotations

import functools
import gc
import logging
import time
from collections.abc import Callable
from typing import (
    Any,
    ParamSpec,
    TypeVar,
    cast,
    overload,
)

try:
    import resource

    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# Type variables for decorators
F = TypeVar("F", bound=Callable[..., Any])
T = TypeVar("T")
P = ParamSpec("P")  # For preserving parameter types in decorators
R = TypeVar("R")  # For preserving return types

# Configure logger
logger = logging.getLogger(__name__)


class ProfilingResult:
    """Container for profiling measurements and metrics."""

    def __init__(self) -> None:
        """Initialize with empty metrics."""
        self.metrics: dict[str, Any] = {
            "start_time_ns": 0,
            "end_time_ns": 0,
            "elapsed_time_s": 0.0,
            "cpu_percent": 0.0,
            "memory_start_mb": 0.0,
            "memory_peak_mb": 0.0,
            "memory_end_mb": 0.0,
            "memory_diff_mb": 0.0,
        }

        # Stats collection enabled flag
        self._enabled = True

    def start(self) -> None:
        """
        Record start metrics including timestamp and memory usage.

        Forces garbage collection to establish a clean baseline for memory measurements.
        """
        if not self._enabled:
            return

        # Force garbage collection to get a clean baseline
        gc.collect()

        # Record starting metrics
        self.metrics["start_time_ns"] = time.time_ns()
        self.metrics["memory_start_mb"] = self._get_memory_usage()

    def end(self) -> None:
        """
        Record end metrics and compute differentials.

        Calculates elapsed time, memory usage changes, and CPU percentage
        if psutil is available.
        """
        if not self._enabled:
            return

        # Record end time and compute elapsed
        self.metrics["end_time_ns"] = time.time_ns()
        self.metrics["elapsed_time_s"] = (
            self.metrics["end_time_ns"] - self.metrics["start_time_ns"]
        ) / 1_000_000_000  # Convert ns to s

        # Memory metrics
        self.metrics["memory_end_mb"] = self._get_memory_usage()
        self.metrics["memory_diff_mb"] = (
            self.metrics["memory_end_mb"] - self.metrics["memory_start_mb"]
        )

        # Get CPU percentage if psutil is available
        if HAS_PSUTIL:
            try:
                self.metrics["cpu_percent"] = psutil.Process().cpu_percent()
            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                pass

    def _get_memory_usage(self) -> float:
        """
        Get current memory usage in MB.

        Prefers psutil for cross-platform support, falls back to resource module
        on Unix-like systems.

        Returns:
            Memory usage in megabytes, or 0.0 if measurement fails
        """
        try:
            if HAS_PSUTIL:
                # Prefer psutil for cross-platform support
                process = psutil.Process()
                mem_info = process.memory_info()
                # Use RSS (Resident Set Size) as the memory metric
                return mem_info.rss / (1024 * 1024)
            else:
                # Fallback to resource module on Unix-like systems
                return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
            OSError,
        ) as e:
            logger.warning("Failed to get memory usage: %s", e)
            return 0.0

    def update_peak_memory(self) -> None:
        """
        Update peak memory usage if current usage exceeds previous peak.

        Should be called periodically during long-running operations to track
        the maximum memory usage throughout the profiling session.
        """
        if not self._enabled:
            return

        current = self._get_memory_usage()
        if current > self.metrics["memory_peak_mb"]:
            self.metrics["memory_peak_mb"] = current

    def disable(self) -> None:
        """
        Disable stats collection.

        When disabled, profiling methods will return early without
        collecting metrics, reducing overhead.
        """
        self._enabled = False

    def enable(self) -> None:
        """
        Enable stats collection.

        Re-enables profiling after it has been disabled, allowing
        metrics to be collected again.
        """
        self._enabled = True

    def __str__(self) -> str:
        """
        Return a formatted string with profiling results.

        Returns:
            Human-readable string showing execution time and memory usage
        """
        return (
            f"Time: {self.metrics['elapsed_time_s']:.2f}s, "
            f"Memory: {self.metrics['memory_diff_mb']:.2f}MB (peak: {self.metrics['memory_peak_mb']:.2f}MB)"
        )


class ProgressReporter:
    """Reports progress for long-running operations."""

    def __init__(
        self,
        total_steps: int,
        callback: Callable[[int, int, dict[str, Any]], None] | None = None,
        report_interval: float = 1.0,
        name: str = "operation",
    ) -> None:
        """Initialize progress reporter.

        Args:
            total_steps: Total number of steps in the operation
            callback: Optional callback to report progress (current, total, metrics)
            report_interval: Minimum seconds between progress reports
            name: Name of the operation for logging
        """
        self.total_steps = total_steps
        self.current_step = 0
        self.callback = callback
        self.report_interval = report_interval
        self.name = name
        self.last_report_time = 0.0
        self.start_time = time.time()
        self.last_metrics: dict[str, Any] = {}

        # Initial report at 0%
        self._maybe_report()

    def update(self, steps: int = 1, **kwargs: Any) -> None:
        """Update progress by incrementing the current step count.

        Args:
            steps: Number of steps completed
            **kwargs: Additional metrics to include in the report
        """
        self.current_step += steps
        self.last_metrics.update(kwargs)
        self._maybe_report()

    def complete(self, **kwargs: Any) -> None:
        """Mark the operation as complete.

        Args:
            **kwargs: Additional metrics to include in the report
        """
        self.current_step = self.total_steps
        self.last_metrics.update(kwargs)
        self._report(force=True)

    def _maybe_report(self) -> None:
        """Report progress if sufficient time has passed since last report."""
        now = time.time()
        if now - self.last_report_time >= self.report_interval:
            self._report()

    def _report(self, force: bool = False) -> None:
        """Report current progress via callback and logging.

        Args:
            force: Force report regardless of time interval
        """
        # If force is True, always report regardless of time interval
        # Otherwise we might want to throttle reports based on frequency
        if not force and (time.time() - self.last_report_time) < self.report_interval:
            return

        # Update the last report time
        self.last_report_time = time.time()

        # Calculate percentage
        percent = (
            min(100, int((self.current_step / self.total_steps) * 100))
            if self.total_steps > 0
            else 0
        )

        # Calculate ETA if we have progress
        metrics = self.last_metrics.copy()
        if self.current_step > 0 and self.current_step < self.total_steps:
            elapsed = time.time() - self.start_time
            eta = (elapsed / self.current_step) * (self.total_steps - self.current_step)
            metrics["eta_seconds"] = eta

        # Add timestamp
        metrics["timestamp"] = time.time()

        # Log progress
        logger.info(
            "%s: %d%% complete (%d/%d steps)",
            self.name,
            percent,
            self.current_step,
            self.total_steps,
        )

        # Call the callback if provided
        if self.callback:
            try:
                self.callback(self.current_step, self.total_steps, metrics)
            except (TypeError, ValueError, RuntimeError) as e:
                logger.error("Progress callback error: %s", e)


@overload
def profile[**P, R](func: Callable[P, R]) -> Callable[P, R]: ...


@overload
def profile(
    *,
    memory: bool = True,
    log_level: int = logging.INFO,
    callback: Callable[[dict[str, Any]], None] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]: ...


def profile[**P, R](
    func: Callable[P, R] | None = None,
    *,
    memory: bool = True,
    log_level: int = logging.INFO,
    callback: Callable[[dict[str, Any]], None] | None = None,
) -> Callable[P, R] | Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator for profiling function execution time and memory usage.

    Can be used as @profile or with parameters @profile(memory=False)

    Args:
        func: The function to decorate
        memory: Whether to track memory usage
        log_level: Level to log profile results
        callback: Optional callback to receive profiling results

    Returns:
        Decorated function
    """

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Create profiling context
            profiler = ProfilingResult()

            # Start profiling
            if not memory:
                profiler.disable()
            profiler.start()

            try:
                # Execute the function
                result = fn(*args, **kwargs)
                return result
            finally:
                # End profiling
                profiler.end()

                # Log results
                logger.log(
                    log_level,
                    "PROFILE %s: %s",
                    getattr(fn, "__qualname__", repr(fn)),
                    str(profiler),
                )

                # Call callback if provided
                if callback:
                    callback(profiler.metrics)

        return cast(Callable[P, R], wrapper)

    if func is not None:
        return decorator(func)
    return decorator


def progressive_task(
    total_steps: int | None = None,
    name: str | None = None,
    report_interval: float = 1.0,
    callback: Callable[[int, int, dict[str, Any]], None] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator for tracking progress of long-running tasks.

    The decorated function receives a progress_reporter argument that
    can be used to update progress during execution.

    Args:
        total_steps: Total number of steps or None to determine from first arg
        name: Operation name for logging
        report_interval: Minimum seconds between progress reports
        callback: Optional callback for progress updates

    Returns:
        Decorator function
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        func_qualname = getattr(func, "__qualname__", getattr(func, "__name__", repr(func)))

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Determine operation name
            operation_name = name or func_qualname

            # Determine total steps
            steps = total_steps
            if steps is None and args and isinstance(args[0], (int, float)):
                steps = int(args[0])
            if steps is None:
                steps = 100  # Default if we can't determine

            # Create progress reporter
            reporter = ProgressReporter(
                total_steps=steps,
                callback=callback,
                report_interval=report_interval,
                name=operation_name,
            )

            # Add reporter to kwargs — cast needed because ParamSpec kwargs
            # doesn't allow arbitrary key assignment
            kw = cast(dict[str, Any], kwargs)
            kw["progress_reporter"] = reporter

            # Execute function with progress tracking
            try:
                result = func(*args, **kwargs)
            finally:
                # Ensure we mark as complete
                reporter.complete()

            return result

        return cast(Callable[P, R], wrapper)

    return decorator
