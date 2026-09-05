"""状态接口测试 — GET /api/v1/status"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

import dochris
from tests.test_api.conftest import _make_manifest, _write_manifest

pytestmark = pytest.mark.fast


class TestStatusEndpoint:
    """状态接口测试"""

    def test_status_returns_workspace_info(self, client, tmp_workspace) -> None:
        """状态接口返回工作区信息"""
        # 写入两个 manifest
        _write_manifest(tmp_workspace, _make_manifest("SRC-0001", status="compiled"))
        _write_manifest(
            tmp_workspace, _make_manifest("SRC-0002", status="ingested", file_type="audio")
        )

        mock_settings = type(
            "Settings",
            (),
            {
                "workspace": tmp_workspace,
                "model": "test-model",
                "query_model": "test-query-model",
                "api_base": "https://test.api",
                "max_concurrency": 3,
                "min_quality_score": 85,
                "api_key": "test-key",
                "llm_provider": "openai",
                "llm_temperature": 0.3,
            },
        )()

        with (
            patch("dochris.api.routes.status.get_settings", return_value=mock_settings),
            patch("dochris.api.routes.status.get_all_manifests") as mock_manifests,
        ):
            mock_manifests.return_value = [
                _make_manifest("SRC-0001", status="compiled"),
                _make_manifest("SRC-0002", status="ingested", file_type="audio"),
            ]

            resp = client.get("/api/v1/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["workspace"] == str(tmp_workspace)
        assert data["config"]["model"] == "test-model"
        assert data["config"]["has_api_key"] is True
        assert data["manifests"]["total"] == 2
        assert data["manifests"]["compiled"] == 1
        assert data["manifests"]["ingested"] == 1

    def test_status_empty_workspace(self, client, tmp_workspace) -> None:
        """空工作区返回零计数"""
        mock_settings = type(
            "Settings",
            (),
            {
                "workspace": tmp_workspace,
                "model": "test",
                "query_model": "test",
                "api_base": "https://test",
                "max_concurrency": 1,
                "min_quality_score": 85,
                "api_key": None,
                "llm_provider": "openai",
                "llm_temperature": 0.3,
            },
        )()

        with (
            patch("dochris.api.routes.status.get_settings", return_value=mock_settings),
            patch("dochris.api.routes.status.get_all_manifests", return_value=[]),
        ):
            resp = client.get("/api/v1/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["manifests"]["total"] == 0
        assert data["config"]["has_api_key"] is False

    def test_health_endpoint(self, client) -> None:
        """健康检查端点"""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_readiness_reports_a_usable_workspace(self, client, tmp_workspace) -> None:
        """readiness 只在运行所需目录存在且可写时返回 ready"""
        settings = SimpleNamespace(workspace=tmp_workspace)

        with patch("dochris.api.app.get_settings", return_value=settings, create=True):
            resp = client.get("/ready")

        assert resp.status_code == 200
        assert resp.json() == {
            "status": "ready",
            "version": dochris.__version__,
            "checks": {
                "workspace": {
                    "status": "ok",
                    "path": str(tmp_workspace),
                    "writable": True,
                },
                "directories": {
                    "status": "ok",
                    "missing": [],
                    "unwritable": [],
                },
            },
        }

    def test_readiness_rejects_a_missing_workspace(self, client, tmp_path) -> None:
        """缺失工作区时 readiness 返回稳定的 503 诊断，不假装服务可用"""
        missing_workspace = tmp_path / "not-created"
        settings = SimpleNamespace(workspace=missing_workspace)

        with patch("dochris.api.app.get_settings", return_value=settings, create=True):
            resp = client.get("/ready")

        assert resp.status_code == 503
        assert resp.json() == {
            "status": "not_ready",
            "version": dochris.__version__,
            "checks": {
                "workspace": {
                    "status": "missing",
                    "path": str(missing_workspace),
                    "writable": False,
                },
                "directories": {
                    "status": "missing",
                    "missing": [
                        "curated",
                        "manifests/sources",
                        "outputs",
                        "raw",
                        "wiki",
                    ],
                    "unwritable": [],
                },
            },
        }
