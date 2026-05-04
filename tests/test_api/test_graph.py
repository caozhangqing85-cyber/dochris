"""知识图谱 API 测试"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from dochris.api.app import create_app


@pytest.fixture
def client() -> TestClient:
    """创建测试客户端"""
    app = create_app()
    return TestClient(app)


def _setup_workspace(workspace: Path) -> None:
    """创建带数据的临时工作区"""
    manifests_dir = workspace / "manifests" / "sources"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    (workspace / "wiki" / "summaries").mkdir(parents=True, exist_ok=True)
    (workspace / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)

    manifest = {
        "id": "SRC-0001",
        "title": "深度学习入门",
        "type": "article",
        "status": "compiled",
        "quality_score": 90,
        "tags": ["AI"],
        "compiled_summary": {"concepts": ["神经网络"]},
    }
    (manifests_dir / "SRC-0001.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )

    (workspace / "wiki" / "concepts" / "神经网络.md").write_text("# 神经网络\n", encoding="utf-8")


def _unwrap(resp_json: dict) -> dict:
    """从统一响应中提取 data 字段"""
    return resp_json["data"]


class TestGraphAPI:
    """知识图谱 API 端点测试"""

    def test_get_graph_json(self, client: TestClient, tmp_path: Path) -> None:
        """测试获取 JSON 格式图谱"""
        with patch("dochris.api.routes.graph.get_settings") as gs:
            gs.return_value.workspace = tmp_path
            resp = client.get("/api/v1/graph?format=json")
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
            assert "version" in body
            data = _unwrap(body)
            assert "nodes" in data
            assert "edges" in data

    def test_get_graph_stats(self, client: TestClient, tmp_path: Path) -> None:
        """测试获取图谱统计"""
        with patch("dochris.api.routes.graph.get_settings") as gs:
            gs.return_value.workspace = tmp_path
            resp = client.get("/api/v1/graph?format=stats")
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
            data = _unwrap(body)
            assert "total_nodes" in data
            assert "node_types" in data

    def test_get_graph_d3(self, client: TestClient, tmp_path: Path) -> None:
        """测试获取 D3 格式图谱"""
        _setup_workspace(tmp_path)
        with patch("dochris.api.routes.graph.get_settings") as gs:
            gs.return_value.workspace = tmp_path
            resp = client.get("/api/v1/graph?format=d3")
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
            data = _unwrap(body)
            assert "nodes" in data
            assert "links" in data
            assert data["nodes"][0]["group"] in ("source", "concept", "summary")

    def test_search_graph(self, client: TestClient, tmp_path: Path) -> None:
        """测试图谱搜索"""
        _setup_workspace(tmp_path)
        with patch("dochris.api.routes.graph.get_settings") as gs:
            gs.return_value.workspace = tmp_path
            resp = client.get("/api/v1/graph/search?q=深度&limit=5")
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
            data = _unwrap(body)
            assert "query" in data
            assert data["query"] == "深度"
            assert "nodes" in data

    def test_get_node_not_found(self, client: TestClient, tmp_path: Path) -> None:
        """测试获取不存在的节点"""
        with patch("dochris.api.routes.graph.get_settings") as gs:
            gs.return_value.workspace = tmp_path
            resp = client.get("/api/v1/graph/node/NONEXISTENT")
            assert resp.status_code == 404
            detail = resp.json()["detail"]
            assert detail["success"] is False
            assert "error" in detail

    def test_get_node_with_data(self, client: TestClient, tmp_path: Path) -> None:
        """测试获取存在的节点"""
        _setup_workspace(tmp_path)
        with patch("dochris.api.routes.graph.get_settings") as gs:
            gs.return_value.workspace = tmp_path
            resp = client.get("/api/v1/graph/node/SRC-0001")
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
            data = _unwrap(body)
            assert data["node"] is not None
            assert data["node"]["id"] == "SRC-0001"
            assert "neighbors" in data

    def test_graph_with_data(self, client: TestClient, tmp_path: Path) -> None:
        """测试有数据的图谱"""
        _setup_workspace(tmp_path)
        with patch("dochris.api.routes.graph.get_settings") as gs:
            gs.return_value.workspace = tmp_path
            resp = client.get("/api/v1/graph?format=json")
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
            data = _unwrap(body)
            assert len(data["nodes"]) >= 2  # 至少有 source 和 concept
