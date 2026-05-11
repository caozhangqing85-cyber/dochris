"""编译接口测试 — POST /api/v1/compile"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from dochris.api.app import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


class TestCompileEndpoint:
    """编译接口测试"""

    def test_compile_no_work(self, client) -> None:
        """没有待编译文档"""
        with (
            patch("dochris.api.routes.compile.get_default_workspace"),
            patch("dochris.api.routes.compile.get_all_manifests", return_value=[]),
        ):
            resp = client.post("/api/v1/compile", json={"concurrency": 1})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "no_work"
        assert data["total"] == 0

    def test_compile_dry_run(self, client) -> None:
        """模拟运行"""
        manifests = [{"id": f"SRC-{i:04d}", "status": "ingested"} for i in range(3)]

        with (
            patch("dochris.api.routes.compile.get_default_workspace"),
            patch("dochris.api.routes.compile.get_all_manifests", return_value=manifests),
        ):
            resp = client.post("/api/v1/compile", json={"dry_run": True, "concurrency": 1})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "dry_run"
        assert data["total"] == 3

    def test_compile_with_limit(self, client) -> None:
        """限制编译数量"""
        manifests = [{"id": f"SRC-{i:04d}", "status": "ingested"} for i in range(10)]

        with (
            patch("dochris.api.routes.compile.get_default_workspace"),
            patch("dochris.api.routes.compile.get_all_manifests", return_value=manifests),
            patch(
                "dochris.api.routes.compile.do_compile_all", new_callable=AsyncMock
            ) as mock_compile,
        ):
            resp = client.post("/api/v1/compile", json={"limit": 5, "concurrency": 2})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        mock_compile.assert_called_once_with(max_concurrent=2, limit=5, dry_run=False)

    def test_compile_background_error_is_logged(self, client) -> None:
        """后台编译失败不阻塞 HTTP 响应"""
        manifests = [{"id": "SRC-0001", "status": "ingested"}]

        with (
            patch("dochris.api.routes.compile.get_default_workspace"),
            patch("dochris.api.routes.compile.get_all_manifests", return_value=manifests),
            patch(
                "dochris.api.routes.compile.do_compile_all",
                new_callable=AsyncMock,
                side_effect=RuntimeError("编译失败"),
            ),
        ):
            resp = client.post("/api/v1/compile", json={"concurrency": 1})

        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    def test_compile_default_concurrency(self, client) -> None:
        """默认并发数为 1"""
        manifests = [{"id": "SRC-0001", "status": "ingested"}]

        with (
            patch("dochris.api.routes.compile.get_default_workspace"),
            patch("dochris.api.routes.compile.get_all_manifests", return_value=manifests),
            patch(
                "dochris.api.routes.compile.do_compile_all", new_callable=AsyncMock
            ) as mock_compile,
        ):
            resp = client.post("/api/v1/compile", json={})

        assert resp.status_code == 200
        call_kwargs = mock_compile.call_args
        assert call_kwargs[1]["max_concurrent"] == 1
