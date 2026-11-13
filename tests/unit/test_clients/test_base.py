"""Tests for coding_client.clients.base — ServiceClient and ServiceError."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from coding_client.clients.base import ServiceClient, ServiceError

# ---------------------------------------------------------------------------
# ServiceError
# ---------------------------------------------------------------------------


class TestServiceError:
    """Test ServiceError exception attributes."""

    def test_stores_status_code(self):
        err = ServiceError(404, "not found")
        assert err.status_code == 404

    def test_stores_message(self):
        err = ServiceError(500, "server error")
        assert str(err) == "server error"

    def test_stores_body_none_by_default(self):
        err = ServiceError(400, "bad request")
        assert err.body is None

    def test_stores_body_dict(self):
        body = {"detail": "invalid"}
        err = ServiceError(422, "unprocessable", body=body)
        assert err.body == body

    def test_is_exception(self):
        err = ServiceError(500, "boom")
        assert isinstance(err, Exception)


# ---------------------------------------------------------------------------
# ServiceClient.__init__
# ---------------------------------------------------------------------------


class TestServiceClientInit:
    """Test constructor defaults and URL normalisation."""

    def test_base_url_stored(self):
        client = ServiceClient("http://localhost:8000")
        assert client.base_url == "http://localhost:8000"

    def test_trailing_slash_stripped(self):
        client = ServiceClient("http://example.com/")
        assert client.base_url == "http://example.com"

    def test_multiple_trailing_slashes_stripped(self):
        client = ServiceClient("http://example.com///")
        assert client.base_url == "http://example.com"

    def test_default_timeout(self):
        client = ServiceClient("http://x")
        assert client.timeout == 30.0

    def test_custom_timeout(self):
        client = ServiceClient("http://x", timeout=10.0)
        assert client.timeout == 10.0

    def test_default_max_retries(self):
        client = ServiceClient("http://x")
        assert client.max_retries == 3

    def test_custom_max_retries(self):
        client = ServiceClient("http://x", max_retries=5)
        assert client.max_retries == 5

    def test_client_starts_none(self):
        client = ServiceClient("http://x")
        assert client._client is None


# ---------------------------------------------------------------------------
# ServiceClient._ensure_client
# ---------------------------------------------------------------------------


class TestEnsureClient:
    """Test lazy httpx.AsyncClient creation."""

    async def test_creates_client(self):
        sc = ServiceClient("http://localhost:9000")
        result = await sc._ensure_client()
        assert isinstance(result, httpx.AsyncClient)
        await sc.close()

    async def test_reuses_existing_client(self):
        sc = ServiceClient("http://localhost:9000")
        first = await sc._ensure_client()
        second = await sc._ensure_client()
        assert first is second
        await sc.close()

    async def test_recreates_after_close(self):
        sc = ServiceClient("http://localhost:9000")
        first = await sc._ensure_client()
        await sc.close()
        second = await sc._ensure_client()
        assert first is not second
        await sc.close()


# ---------------------------------------------------------------------------
# ServiceClient._request
# ---------------------------------------------------------------------------


class TestRequest:
    """Test _request method with mocked httpx transport."""

    def _mock_response(
        self,
        status_code: int = 200,
        json_data: dict | None = None,
        text: str = "",
        content: bytes | None = None,
    ) -> MagicMock:
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = status_code
        if json_data is not None:
            resp.json.return_value = json_data
            resp.content = b'{"ok": true}'
            resp.text = '{"ok": true}'
        elif content is not None:
            resp.content = content
            resp.text = text
            resp.json.side_effect = ValueError("not json")
        else:
            resp.content = content if content is not None else (text.encode() if text else b"")
            resp.text = text
            resp.json.side_effect = ValueError("not json")
        return resp

    async def test_200_json_response(self):
        sc = ServiceClient("http://svc:8000")
        mock_resp = self._mock_response(200, json_data={"result": "ok"})
        with patch.object(sc, "_ensure_client", new_callable=AsyncMock) as mock_ec:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_ec.return_value = mock_client

            result = await sc._request("GET", "/api/data")
            assert result == {"result": "ok"}
            mock_client.request.assert_called_once_with(
                "GET",
                "/api/data",
                headers=None,
            )

    async def test_204_returns_none(self):
        sc = ServiceClient("http://svc:8000")
        mock_resp = self._mock_response(204)
        mock_resp.content = b""
        with patch.object(sc, "_ensure_client", new_callable=AsyncMock) as mock_ec:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_ec.return_value = mock_client

            result = await sc._request("DELETE", "/api/item/1")
            assert result is None

    async def test_empty_body_returns_none(self):
        sc = ServiceClient("http://svc:8000")
        mock_resp = self._mock_response(200)
        mock_resp.content = b""
        mock_resp.status_code = 200
        with patch.object(sc, "_ensure_client", new_callable=AsyncMock) as mock_ec:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_ec.return_value = mock_client

            result = await sc._request("POST", "/api/empty")
            assert result is None

    async def test_non_json_returns_text(self):
        sc = ServiceClient("http://svc:8000")
        mock_resp = self._mock_response(200, text="plain text", content=b"plain text")
        with patch.object(sc, "_ensure_client", new_callable=AsyncMock) as mock_ec:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_ec.return_value = mock_client

            result = await sc._request("GET", "/api/text")
            assert result == "plain text"

    async def test_4xx_raises_service_error(self):
        sc = ServiceClient("http://svc:8000")
        mock_resp = self._mock_response(404, json_data={"detail": "not found"})
        with patch.object(sc, "_ensure_client", new_callable=AsyncMock) as mock_ec:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_ec.return_value = mock_client

            with pytest.raises(ServiceError) as exc_info:
                await sc._request("GET", "/api/missing")
            assert exc_info.value.status_code == 404
            assert exc_info.value.body == {"detail": "not found"}

    async def test_5xx_raises_service_error(self):
        sc = ServiceClient("http://svc:8000")
        mock_resp = self._mock_response(500, text="internal error", content=b"internal error")
        with patch.object(sc, "_ensure_client", new_callable=AsyncMock) as mock_ec:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_ec.return_value = mock_client

            with pytest.raises(ServiceError) as exc_info:
                await sc._request("GET", "/api/fail")
            assert exc_info.value.status_code == 500
            assert exc_info.value.body == "internal error"

    async def test_retries_on_connect_error(self):
        sc = ServiceClient("http://svc:8000", max_retries=2)
        mock_resp = self._mock_response(200, json_data={"ok": True})
        with patch.object(sc, "_ensure_client", new_callable=AsyncMock) as mock_ec:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(
                side_effect=[httpx.ConnectError("conn refused"), mock_resp]
            )
            mock_ec.return_value = mock_client

            result = await sc._request("GET", "/api/retry")
            assert result == {"ok": True}
            assert mock_client.request.call_count == 2

    async def test_retries_on_read_timeout(self):
        sc = ServiceClient("http://svc:8000", max_retries=2)
        mock_resp = self._mock_response(200, json_data={"ok": True})
        with patch.object(sc, "_ensure_client", new_callable=AsyncMock) as mock_ec:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(side_effect=[httpx.ReadTimeout("timeout"), mock_resp])
            mock_ec.return_value = mock_client

            result = await sc._request("GET", "/api/slow")
            assert result == {"ok": True}
            assert mock_client.request.call_count == 2

    async def test_exhausted_retries_raises(self):
        sc = ServiceClient("http://svc:8000", max_retries=2)
        with patch.object(sc, "_ensure_client", new_callable=AsyncMock) as mock_ec:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(side_effect=httpx.ConnectError("conn refused"))
            mock_ec.return_value = mock_client

            with pytest.raises(httpx.ConnectError):
                await sc._request("GET", "/api/down")
            assert mock_client.request.call_count == 2

    async def test_max_attempts_overrides_max_retries(self):
        sc = ServiceClient("http://svc:8000", max_retries=3)
        with patch.object(sc, "_ensure_client", new_callable=AsyncMock) as mock_ec:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(side_effect=httpx.ReadTimeout("timeout"))
            mock_ec.return_value = mock_client

            with pytest.raises(httpx.ReadTimeout):
                await sc._request("POST", "/api/submit", max_attempts=1, json={"a": 1})
            assert mock_client.request.call_count == 1
            # max_attempts is consumed by the client, never forwarded to httpx
            assert "max_attempts" not in mock_client.request.call_args.kwargs
            assert mock_client.request.call_args.kwargs["json"] == {"a": 1}

    async def test_passes_headers(self):
        sc = ServiceClient("http://svc:8000")
        mock_resp = self._mock_response(200, json_data={})
        with patch.object(sc, "_ensure_client", new_callable=AsyncMock) as mock_ec:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_ec.return_value = mock_client

            await sc._request("GET", "/api/x", headers={"X-Token": "abc"})
            mock_client.request.assert_called_once_with(
                "GET",
                "/api/x",
                headers={"X-Token": "abc"},
            )

    async def test_passes_kwargs(self):
        sc = ServiceClient("http://svc:8000")
        mock_resp = self._mock_response(200, json_data={})
        with patch.object(sc, "_ensure_client", new_callable=AsyncMock) as mock_ec:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_ec.return_value = mock_client

            await sc._request("POST", "/api/x", json={"key": "val"})
            mock_client.request.assert_called_once_with(
                "POST",
                "/api/x",
                headers=None,
                json={"key": "val"},
            )


# ---------------------------------------------------------------------------
# Convenience methods: get/post/put/delete/patch
# ---------------------------------------------------------------------------


class TestConvenienceMethods:
    """Test that get/post/put/delete/patch delegate to _request."""

    async def test_get_calls_request(self):
        sc = ServiceClient("http://x")
        with patch.object(sc, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"ok": True}
            result = await sc.get("/path", params={"q": "1"})
            mock_req.assert_called_once_with("GET", "/path", headers=None, params={"q": "1"})
            assert result == {"ok": True}

    async def test_post_calls_request(self):
        sc = ServiceClient("http://x")
        with patch.object(sc, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"id": 1}
            result = await sc.post("/path", json={"data": "x"})
            mock_req.assert_called_once_with("POST", "/path", headers=None, json={"data": "x"})
            assert result == {"id": 1}

    async def test_put_calls_request(self):
        sc = ServiceClient("http://x")
        with patch.object(sc, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = None
            result = await sc.put("/path", json={"data": "y"})
            mock_req.assert_called_once_with("PUT", "/path", headers=None, json={"data": "y"})
            assert result is None

    async def test_delete_calls_request(self):
        sc = ServiceClient("http://x")
        with patch.object(sc, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = None
            result = await sc.delete("/path")
            mock_req.assert_called_once_with("DELETE", "/path", headers=None)
            assert result is None

    async def test_patch_calls_request(self):
        sc = ServiceClient("http://x")
        with patch.object(sc, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"updated": True}
            result = await sc.patch("/path", json={"field": "v"})
            mock_req.assert_called_once_with("PATCH", "/path", headers=None, json={"field": "v"})
            assert result == {"updated": True}


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    """Test health_check returns bool."""

    async def test_returns_true_on_success(self):
        sc = ServiceClient("http://x")
        with patch.object(sc, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"status": "ok"}
            assert await sc.health_check() is True
            mock_get.assert_called_once_with("/health")

    async def test_returns_false_on_error(self):
        sc = ServiceClient("http://x")
        with patch.object(sc, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = ServiceError(503, "down")
            assert await sc.health_check() is False

    async def test_returns_false_on_connection_error(self):
        sc = ServiceClient("http://x")
        with patch.object(sc, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("refused")
            assert await sc.health_check() is False


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------


class TestClose:
    """Test close() shuts down the HTTP client."""

    async def test_close_sets_client_none(self):
        sc = ServiceClient("http://x")
        sc._client = AsyncMock(spec=httpx.AsyncClient)
        sc._client.is_closed = False
        sc._client.aclose = AsyncMock()
        await sc.close()
        sc._client_original = None  # it was set to None
        # after close, _client should be None
        assert sc._client is None

    async def test_close_calls_aclose(self):
        sc = ServiceClient("http://x")
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()
        sc._client = mock_client
        await sc.close()
        mock_client.aclose.assert_called_once()

    async def test_close_noop_when_no_client(self):
        sc = ServiceClient("http://x")
        await sc.close()  # should not raise
        assert sc._client is None

    async def test_close_noop_when_already_closed(self):
        sc = ServiceClient("http://x")
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.is_closed = True
        sc._client = mock_client
        await sc.close()
        mock_client.aclose.assert_not_called()


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


class TestContextManager:
    """Test async with ServiceClient(...)."""

    async def test_context_manager_enter_returns_self(self):
        sc = ServiceClient("http://x")
        with patch.object(sc, "_ensure_client", new_callable=AsyncMock):
            async with sc as client:
                assert client is sc

    async def test_context_manager_calls_close_on_exit(self):
        sc = ServiceClient("http://x")
        with (
            patch.object(sc, "_ensure_client", new_callable=AsyncMock),
            patch.object(sc, "close", new_callable=AsyncMock) as mock_close,
        ):
            async with sc:
                pass
            mock_close.assert_called_once()
