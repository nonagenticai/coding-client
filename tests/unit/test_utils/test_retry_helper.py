"""Tests for coding_client.utils.retry_helper module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from coding_client.utils.retry_helper import (
    DATABASE_RETRYABLE_EXCEPTIONS,
    DOCKER_RETRYABLE_EXCEPTIONS,
    NETWORK_RETRYABLE_EXCEPTIONS,
    RetryConfig,
    RetryHelper,
    retry_database,
    retry_docker,
    retry_network,
    retry_with_config,
    with_retry,
)

# ---------------------------------------------------------------------------
# RetryConfig
# ---------------------------------------------------------------------------


class TestRetryConfig:
    """Tests for RetryConfig dataclass-like configuration."""

    def test_default_values(self):
        cfg = RetryConfig()
        assert cfg.max_attempts == 3
        assert cfg.initial_delay == 1.0
        assert cfg.backoff_factor == 2.0
        assert cfg.max_delay == 60.0
        assert cfg.retryable_exceptions == (Exception,)
        assert cfg.retry_on_result is None

    def test_custom_values(self):
        cfg = RetryConfig(
            max_attempts=5,
            initial_delay=0.5,
            backoff_factor=3.0,
            max_delay=120.0,
            retryable_exceptions=(ValueError,),
        )
        assert cfg.max_attempts == 5
        assert cfg.initial_delay == 0.5
        assert cfg.backoff_factor == 3.0
        assert cfg.max_delay == 120.0
        assert cfg.retryable_exceptions == (ValueError,)

    def test_retry_on_result_callback(self):
        callback = lambda r: r is None  # noqa: E731
        cfg = RetryConfig(retry_on_result=callback)
        assert cfg.retry_on_result is callback


# ---------------------------------------------------------------------------
# RetryHelper.calculate_delay
# ---------------------------------------------------------------------------


class TestCalculateDelay:
    """Tests for exponential backoff delay calculation."""

    def test_attempt_zero(self):
        delay = RetryHelper.calculate_delay(0, initial_delay=1.0, backoff_factor=2.0)
        assert delay == 1.0

    def test_attempt_one(self):
        delay = RetryHelper.calculate_delay(1, initial_delay=1.0, backoff_factor=2.0)
        assert delay == 2.0

    def test_attempt_two(self):
        delay = RetryHelper.calculate_delay(2, initial_delay=1.0, backoff_factor=2.0)
        assert delay == 4.0

    def test_respects_max_delay(self):
        delay = RetryHelper.calculate_delay(
            10, initial_delay=1.0, backoff_factor=2.0, max_delay=5.0
        )
        assert delay == 5.0

    def test_custom_initial_and_factor(self):
        delay = RetryHelper.calculate_delay(
            2, initial_delay=0.5, backoff_factor=3.0, max_delay=100.0
        )
        assert delay == pytest.approx(0.5 * 9)


# ---------------------------------------------------------------------------
# RetryHelper.retry_async
# ---------------------------------------------------------------------------


class TestRetryAsync:
    """Tests for async retry execution."""

    async def test_succeeds_first_attempt(self):
        func = AsyncMock(return_value="ok")
        result = await RetryHelper.retry_async(func)
        assert result == "ok"
        assert func.await_count == 1

    async def test_succeeds_after_transient_failure(self):
        func = AsyncMock(side_effect=[ConnectionError("fail"), "ok"])
        cfg = RetryConfig(initial_delay=0, retryable_exceptions=(ConnectionError,))
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await RetryHelper.retry_async(func, config=cfg)
        assert result == "ok"
        assert func.await_count == 2

    async def test_raises_after_max_retries(self):
        func = AsyncMock(side_effect=ConnectionError("fail"))
        cfg = RetryConfig(max_attempts=2, initial_delay=0, retryable_exceptions=(ConnectionError,))
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ConnectionError, match="fail"):
                await RetryHelper.retry_async(func, config=cfg)
        assert func.await_count == 2

    async def test_non_retryable_exception_raises_immediately(self):
        func = AsyncMock(side_effect=TypeError("bad type"))
        cfg = RetryConfig(initial_delay=0, retryable_exceptions=(ConnectionError,))
        with pytest.raises(TypeError, match="bad type"):
            await RetryHelper.retry_async(func, config=cfg)
        assert func.await_count == 1

    async def test_retry_on_result_callback(self):
        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            return None if call_count < 3 else "done"

        cfg = RetryConfig(
            max_attempts=5,
            initial_delay=0,
            retry_on_result=lambda r: r is None,
        )
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await RetryHelper.retry_async(flaky, config=cfg)
        assert result == "done"
        assert call_count == 3


# ---------------------------------------------------------------------------
# RetryHelper.retry_sync
# ---------------------------------------------------------------------------


class TestRetrySync:
    """Tests for synchronous retry execution."""

    def test_succeeds_first_attempt(self):
        func = MagicMock(return_value="ok")
        result = RetryHelper.retry_sync(func)
        assert result == "ok"
        func.assert_called_once()

    def test_succeeds_after_transient_failure(self):
        func = MagicMock(side_effect=[OSError("fail"), "ok"])
        cfg = RetryConfig(initial_delay=0, retryable_exceptions=(OSError,))
        with patch("time.sleep"):
            result = RetryHelper.retry_sync(func, config=cfg)
        assert result == "ok"
        assert func.call_count == 2

    def test_raises_after_max_retries(self):
        func = MagicMock(side_effect=OSError("fail"))
        cfg = RetryConfig(max_attempts=2, initial_delay=0, retryable_exceptions=(OSError,))
        with patch("time.sleep"):
            with pytest.raises(OSError, match="fail"):
                RetryHelper.retry_sync(func, config=cfg)
        assert func.call_count == 2


# ---------------------------------------------------------------------------
# RetryHelper.poll_until
# ---------------------------------------------------------------------------


class TestPollUntil:
    """Tests for polling until a condition is met."""

    async def test_condition_met_immediately(self):
        func = MagicMock(return_value=True)
        result = await RetryHelper.poll_until(func, condition=bool, max_attempts=5)
        assert result is True
        func.assert_called_once()

    async def test_condition_met_after_several_polls(self):
        results = iter([False, False, True])
        func = MagicMock(side_effect=lambda: next(results))
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await RetryHelper.poll_until(
                func, condition=bool, max_attempts=5, poll_interval=0
            )
        assert result is True
        assert func.call_count == 3

    async def test_raises_timeout_after_max_attempts(self):
        func = MagicMock(return_value=False)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(TimeoutError, match="not met after"):
                await RetryHelper.poll_until(func, condition=bool, max_attempts=3, poll_interval=0)

    async def test_async_check_func(self):
        async_func = AsyncMock(return_value=42)
        result = await RetryHelper.poll_until(
            async_func, condition=lambda x: x == 42, max_attempts=5
        )
        assert result == 42


# ---------------------------------------------------------------------------
# Tenacity-based decorator: retry_docker
# ---------------------------------------------------------------------------


class TestRetryDocker:
    """Tests for @retry_docker decorator."""

    async def test_async_success_first_try(self):
        @retry_docker(max_attempts=3, min_wait=0, max_wait=0)
        async def do_docker():
            return "pulled"

        assert await do_docker() == "pulled"

    async def test_async_retries_on_connection_error(self):
        call_count = 0

        @retry_docker(max_attempts=3, min_wait=0, max_wait=0.01)
        async def do_docker():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("timeout")
            return "ok"

        result = await do_docker()
        assert result == "ok"
        assert call_count == 3

    def test_sync_success_first_try(self):
        @retry_docker(max_attempts=2, min_wait=0, max_wait=0)
        def do_docker():
            return "done"

        assert do_docker() == "done"

    def test_exception_categories_contain_expected(self):
        assert ConnectionError in DOCKER_RETRYABLE_EXCEPTIONS
        assert TimeoutError in DOCKER_RETRYABLE_EXCEPTIONS
        assert OSError in DOCKER_RETRYABLE_EXCEPTIONS


# ---------------------------------------------------------------------------
# Tenacity-based decorator: retry_network
# ---------------------------------------------------------------------------


class TestRetryNetwork:
    """Tests for @retry_network decorator."""

    async def test_additional_exceptions_parameter(self):
        call_count = 0

        @retry_network(
            max_attempts=2, min_wait=0, max_wait=0.01, additional_exceptions=[RuntimeError]
        )
        async def net_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("custom")
            return "ok"

        result = await net_call()
        assert result == "ok"

    def test_exception_categories(self):
        assert ConnectionError in NETWORK_RETRYABLE_EXCEPTIONS
        assert ConnectionRefusedError in NETWORK_RETRYABLE_EXCEPTIONS
        assert ConnectionResetError in NETWORK_RETRYABLE_EXCEPTIONS
        assert TimeoutError in NETWORK_RETRYABLE_EXCEPTIONS


# ---------------------------------------------------------------------------
# Tenacity-based decorator: retry_database
# ---------------------------------------------------------------------------


class TestRetryDatabase:
    """Tests for @retry_database decorator (promoted from coding-containers)."""

    async def test_async_success_first_try(self):
        @retry_database(max_attempts=3, min_wait=0, max_wait=0)
        async def query():
            return "rows"

        assert await query() == "rows"

    async def test_async_retries_on_operational_error(self):
        import sqlite3

        call_count = 0

        @retry_database(max_attempts=3, min_wait=0, max_wait=0.01)
        async def query():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise sqlite3.OperationalError("database is locked")
            return "ok"

        assert await query() == "ok"
        assert call_count == 3

    def test_sync_success_first_try(self):
        @retry_database(max_attempts=2, min_wait=0, max_wait=0)
        def query():
            return "done"

        assert query() == "done"

    def test_exception_categories_contain_expected(self):
        import sqlite3

        assert sqlite3.OperationalError in DATABASE_RETRYABLE_EXCEPTIONS
        assert OSError in DATABASE_RETRYABLE_EXCEPTIONS
        assert TimeoutError in DATABASE_RETRYABLE_EXCEPTIONS


# ---------------------------------------------------------------------------
# retry_with_config (generic)
# ---------------------------------------------------------------------------


class TestRetryWithConfig:
    """Tests for generic retry_with_config decorator."""

    async def test_exponential_strategy(self):
        call_count = 0

        @retry_with_config(
            max_attempts=3,
            wait_strategy="exponential",
            min_wait=0,
            max_wait=0.01,
            exceptions=[ValueError],
        )
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("bad")
            return "ok"

        result = await flaky()
        assert result == "ok"

    def test_fixed_strategy_sync(self):
        call_count = 0

        @retry_with_config(
            max_attempts=2,
            wait_strategy="fixed",
            fixed_wait=0,
            exceptions=[RuntimeError],
        )
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("oops")
            return "done"

        assert flaky() == "done"


# ---------------------------------------------------------------------------
# with_retry (legacy decorator)
# ---------------------------------------------------------------------------


class TestWithRetry:
    """Tests for legacy with_retry decorator."""

    async def test_async_function(self):
        call_count = 0

        @with_retry(max_attempts=2, initial_delay=0, retryable_exceptions=(ValueError,))
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("x")
            return "ok"

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await flaky()
        assert result == "ok"

    def test_sync_function(self):
        call_count = 0

        @with_retry(max_attempts=2, initial_delay=0, retryable_exceptions=(ValueError,))
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("x")
            return "ok"

        with patch("time.sleep"):
            result = flaky()
        assert result == "ok"
