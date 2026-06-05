"""API 认证中间件测试"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.requests import Request

from dochris.api.auth import verify_api_key


def _make_request(headers: dict | None = None, query_params: dict | None = None) -> Request:
    """构造 FastAPI Request mock"""
    req = MagicMock(spec=Request)
    req.headers = headers or {}
    req.query_params = MagicMock()
    req.query_params.get = (query_params or {}).get
    # 模拟本地客户端地址（与 auth.py 的 allowed_hosts 匹配）
    req.client = MagicMock()
    req.client.host = "127.0.0.1"
    req.url = MagicMock()
    req.url.path = "/api/v1/test"
    return req


# ── 开发模式（未设置 API key）────────────────────────────────


class TestDevMode:
    """未设置 DOCHRIS_API_KEY 时跳过认证"""

    @pytest.mark.asyncio
    async def test_no_env_key_allows_any_request(self, monkeypatch):
        """环境变量未设置时，任何请求都通过"""
        monkeypatch.delenv("DOCHRIS_API_KEY", raising=False)
        req = _make_request()
        await verify_api_key(req)

    @pytest.mark.asyncio
    async def test_empty_env_key_allows_any_request(self, monkeypatch):
        """环境变量为空字符串时，任何请求都通过"""
        monkeypatch.setenv("DOCHRIS_API_KEY", "")
        req = _make_request()
        await verify_api_key(req)


# ── 正确 key 通过 ─────────────────────────────────────────────


class TestValidKey:
    """正确的 API key 验证通过"""

    @pytest.mark.asyncio
    async def test_header_key_valid(self, monkeypatch):
        """通过 X-API-Key 请求头传递正确的 key"""
        monkeypatch.setenv("DOCHRIS_API_KEY", "secret123")
        req = _make_request(headers={"X-API-Key": "secret123"})
        await verify_api_key(req)

    @pytest.mark.asyncio
    async def test_query_param_key_valid(self, monkeypatch):
        """通过 api_key 查询参数传递正确的 key"""
        monkeypatch.setenv("DOCHRIS_API_KEY", "mykey456")
        req = _make_request(query_params={"api_key": "mykey456"})
        await verify_api_key(req)

    @pytest.mark.asyncio
    async def test_header_priority_over_query(self, monkeypatch):
        """请求头优先级高于查询参数"""
        monkeypatch.setenv("DOCHRIS_API_KEY", "correct")
        req = _make_request(headers={"X-API-Key": "correct"}, query_params={"api_key": "wrong"})
        await verify_api_key(req)


# ── 错误 key 拒绝 ─────────────────────────────────────────────


class TestInvalidKey:
    """错误的 API key 被拒绝"""

    @pytest.mark.asyncio
    async def test_wrong_key_raises_401(self, monkeypatch):
        """错误的 key 返回 401"""
        monkeypatch.setenv("DOCHRIS_API_KEY", "correctkey")
        req = _make_request(headers={"X-API-Key": "wrongkey"})
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(req)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_key_detail_message(self, monkeypatch):
        """错误 key 的错误消息包含 'Invalid API key'"""
        monkeypatch.setenv("DOCHRIS_API_KEY", "abc")
        req = _make_request(headers={"X-API-Key": "xyz"})
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(req)
        assert "Invalid API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_missing_key_raises_401(self, monkeypatch):
        """未提供 key 时返回 401"""
        monkeypatch.setenv("DOCHRIS_API_KEY", "required")
        req = _make_request()
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(req)
        assert exc_info.value.status_code == 401


# ── 时序安全性 ────────────────────────────────────────────────


class TestTimingSafety:
    """验证使用 hmac.compare_digest 防止时序侧信道攻击"""

    @pytest.mark.asyncio
    async def test_different_length_key_short_circuits(self, monkeypatch):
        """长度不同的 key 直接拒绝，不走 compare_digest"""
        monkeypatch.setenv("DOCHRIS_API_KEY", "longsecretkey")
        req = _make_request(headers={"X-API-Key": "x"})
        with pytest.raises(HTTPException):
            await verify_api_key(req)

    @pytest.mark.asyncio
    async def test_same_length_wrong_key_uses_compare_digest(self, monkeypatch):
        """相同长度的错误 key 走 compare_digest 路径"""
        monkeypatch.setenv("DOCHRIS_API_KEY", "abcd1234")
        with patch("dochris.api.auth.hmac.compare_digest", return_value=False) as mock_cd:
            req = _make_request(headers={"X-API-Key": "dcba4321"})
            with pytest.raises(HTTPException):
                await verify_api_key(req)
            mock_cd.assert_called_once_with("dcba4321", "abcd1234")

    @pytest.mark.asyncio
    async def test_same_length_correct_key_uses_compare_digest(self, monkeypatch):
        """相同长度的正确 key 走 compare_digest 路径"""
        monkeypatch.setenv("DOCHRIS_API_KEY", "testkey1")
        with patch("dochris.api.auth.hmac.compare_digest", return_value=True) as mock_cd:
            req = _make_request(headers={"X-API-Key": "testkey1"})
            await verify_api_key(req)
            mock_cd.assert_called_once_with("testkey1", "testkey1")
