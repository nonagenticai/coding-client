"""Tests for coding_client.utils.async_timeout module."""

from __future__ import annotations

import asyncio
import contextlib

import pytest
from coding_client.utils.async_timeout import (
    AsyncTaskManager,
    AsyncTimeoutError,
    run_with_timeout,
    task_manager,
    with_timeout,
)
from fastapi import status as http_status

# ---------------------------------------------------------------------------
# AsyncTimeoutError
# ---------------------------------------------------------------------------


class TestAsyncTimeoutError:
    """Tests for custom timeout exception."""

    def test_status_code_is_408(self):
        err = AsyncTimeoutError("timed out", 30.0)
        assert err.status_code == http_status.HTTP_408_REQUEST_TIMEOUT

    def test_detail_includes_timeout_seconds(self):
        err = AsyncTimeoutError("slow op", 15.5)
        assert "15.5s" in err.detail

    def test_timeout_seconds_attribute(self):
        err = AsyncTimeoutError("op", 42.0)
        assert err.timeout_seconds == 42.0

    def test_detail_includes_message(self):
        err = AsyncTimeoutError("Query too slow", 10.0)
        assert "Query too slow" in err.detail


# ---------------------------------------------------------------------------
# run_with_timeout
# ---------------------------------------------------------------------------


class TestRunWithTimeout:
    """Tests for run_with_timeout utility."""

    async def test_completes_within_timeout(self):
        async def quick():
            return "fast"

        result = await run_with_timeout(quick(), 5.0)
        assert result == "fast"

    async def test_raises_on_timeout(self):
        async def slow():
            await asyncio.sleep(10)
            return "never"

        with pytest.raises(AsyncTimeoutError) as exc_info:
            await run_with_timeout(slow(), 0.05, "too slow")
        assert exc_info.value.timeout_seconds == 0.05
        assert "too slow" in exc_info.value.detail

    async def test_propagates_original_exception(self):
        async def broken():
            raise ValueError("broken")

        with pytest.raises(ValueError, match="broken"):
            await run_with_timeout(broken(), 5.0)

    async def test_default_timeout_message(self):
        async def slow():
            await asyncio.sleep(10)

        with pytest.raises(AsyncTimeoutError) as exc_info:
            await run_with_timeout(slow(), 0.05)
        assert "Operation timed out" in exc_info.value.detail


# ---------------------------------------------------------------------------
# with_timeout decorator
# ---------------------------------------------------------------------------


class TestWithTimeoutDecorator:
    """Tests for @with_timeout decorator."""

    async def test_decorated_function_returns_result(self):
        @with_timeout(5.0, "test timeout")
        async def compute():
            return 42

        assert await compute() == 42

    async def test_decorated_function_times_out(self):
        @with_timeout(0.05, "slow compute")
        async def compute():
            await asyncio.sleep(10)
            return 42

        with pytest.raises(AsyncTimeoutError) as exc_info:
            await compute()
        assert "slow compute" in exc_info.value.detail

    async def test_default_message_uses_function_name(self):
        @with_timeout(0.05)
        async def my_special_func():
            await asyncio.sleep(10)

        with pytest.raises(AsyncTimeoutError) as exc_info:
            await my_special_func()
        assert "my_special_func" in exc_info.value.detail

    async def test_preserves_function_name(self):
        @with_timeout(5.0)
        async def original_name():
            pass

        assert original_name.__name__ == "original_name"


# ---------------------------------------------------------------------------
# AsyncTaskManager
# ---------------------------------------------------------------------------


class TestAsyncTaskManager:
    """Tests for background task management."""

    async def test_submit_and_complete_task(self):
        manager = AsyncTaskManager()

        async def work():
            return "result"

        task_id = manager.submit_task("t1", work())
        assert task_id == "t1"

        # Let the task complete
        await asyncio.sleep(0.05)

        status = manager.get_task_status("t1")
        assert status["status"] == "completed"
        assert status["result"] == "result"

    async def test_submit_duplicate_raises(self):
        manager = AsyncTaskManager()

        async def work():
            await asyncio.sleep(1)

        manager.submit_task("dup", work())
        # Let the task start executing so the inner coroutine is awaited
        await asyncio.sleep(0)
        task = manager.tasks["dup"]
        coro = work()
        with pytest.raises(ValueError, match="already exists"):
            manager.submit_task("dup", coro)
        coro.close()

        # Cleanup
        manager.cancel_task("dup")
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def test_failed_task_status(self):
        manager = AsyncTaskManager()

        async def broken():
            raise RuntimeError("boom")

        manager.submit_task("err", broken())
        await asyncio.sleep(0.05)

        status = manager.get_task_status("err")
        assert status["status"] == "failed"
        assert "boom" in status["error"]

    async def test_cancel_running_task(self):
        manager = AsyncTaskManager()

        async def long_running():
            await asyncio.sleep(100)

        manager.submit_task("cancel_me", long_running())
        # Let the task start so the inner coroutine is awaited
        await asyncio.sleep(0)
        task = manager.tasks["cancel_me"]
        assert manager.cancel_task("cancel_me") is True
        assert manager.get_task_status("cancel_me")["status"] == "not_found"
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def test_cancel_nonexistent_returns_false(self):
        manager = AsyncTaskManager()
        assert manager.cancel_task("nope") is False

    async def test_status_not_found(self):
        manager = AsyncTaskManager()
        status = manager.get_task_status("nonexistent")
        assert status["status"] == "not_found"

    async def test_running_status(self):
        manager = AsyncTaskManager()

        async def slow():
            await asyncio.sleep(10)

        manager.submit_task("slow_task", slow())
        # Let the task start so the inner coroutine is awaited
        await asyncio.sleep(0)
        status = manager.get_task_status("slow_task")
        assert status["status"] == "running"

        # Cleanup
        task = manager.tasks["slow_task"]
        manager.cancel_task("slow_task")
        with contextlib.suppress(asyncio.CancelledError):
            await task


# ---------------------------------------------------------------------------
# Global task_manager instance
# ---------------------------------------------------------------------------


class TestGlobalTaskManager:
    """Tests for the module-level task_manager singleton."""

    def test_is_async_task_manager_instance(self):
        assert isinstance(task_manager, AsyncTaskManager)

    def test_has_required_attributes(self):
        assert hasattr(task_manager, "tasks")
        assert hasattr(task_manager, "results")
        assert hasattr(task_manager, "errors")
