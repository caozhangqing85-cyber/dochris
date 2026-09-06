"""限流中间件测试（SEC-02）。"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from dochris.api.app import create_app
from dochris.api.ratelimit import SlidingWindowLimiter, rate_limit_per_minute

pytestmark = pytest.mark.fast


def test_rate_limit_disabled_by_default() -> None:
    with patch.dict("os.environ", {}, clear=False):
        assert rate_limit_per_minute() == 0


def test_rate_limit_configured_and_invalid_values() -> None:
    with patch.dict("os.environ", {"DOCHRIS_RATE_LIMIT_PER_MINUTE": "120"}):
        assert rate_limit_per_minute() == 120
    with patch.dict("os.environ", {"DOCHRIS_RATE_LIMIT_PER_MINUTE": "not-a-number"}):
        assert rate_limit_per_minute() == 0
    with patch.dict("os.environ", {"DOCHRIS_RATE_LIMIT_PER_MINUTE": "-5"}):
        assert rate_limit_per_minute() == 0


def test_sliding_window_blocks_over_limit() -> None:
    limiter = SlidingWindowLimiter(max_requests=3, window_seconds=60.0)
    assert limiter.allow("client-a", now=1.0)
    assert limiter.allow("client-a", now=1.1)
    assert limiter.allow("client-a", now=1.2)
    assert not limiter.allow("client-a", now=1.3)
    # 窗口滑动后放行
    assert limiter.allow("client-a", now=61.4)
    # 不同 key 互不影响
    assert limiter.allow("client-b", now=1.4)


def test_limiter_prunes_expired_entries_per_key() -> None:
    """过期条目按 key 清理；活跃 key 常驻（进程生命周期内有界）。"""
    limiter = SlidingWindowLimiter(max_requests=1, window_seconds=1.0)
    for i in range(50):
        limiter.allow(f"client-{i}", now=1.0)
        limiter.allow(f"client-{i}", now=3.0)
    assert len(limiter._hits) == 50  # 每个 key 保留窗口内最新一次


def test_api_returns_429_when_limit_exceeded(monkeypatch) -> None:
    monkeypatch.setenv("DOCHRIS_RATE_LIMIT_PER_MINUTE", "2")
    app = create_app()
    with TestClient(app) as client:
        health = client.get("/health")
        first = client.get("/api/v1/status")
        second = client.get("/api/v1/status")
        third = client.get("/api/v1/status")
    # /health 不限流；/api 限额 2，第三次请求应返回 429
    assert health.status_code == 200
    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429


def test_rate_limit_off_by_default_no_429(client) -> None:
    for _ in range(10):
        resp = client.get("/api/v1/status")
        assert resp.status_code != 429
