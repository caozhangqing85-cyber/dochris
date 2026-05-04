"""查询接口测试 — GET /api/v1/query"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from dochris.api.app import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _mock_query_result(query_str: str = "测试", mode: str = "combined") -> dict:
    """构造模拟查询结果"""
    return {
        "query": query_str,
        "mode": mode,
        "concepts": [
            {
                "title": "费曼技巧",
                "content": "通过教会别人来加深自己的理解",
                "source": "wiki",
                "file_path": "wiki/concepts/费曼技巧.md",
                "manifest_id": "SRC-0001",
                "score": 0.95,
            }
        ],
        "summaries": [
            {
                "title": "费曼学习法",
                "content": "一种高效的学习方法",
                "source": "outputs",
                "file_path": "outputs/summaries/费曼学习法.md",
                "manifest_id": "SRC-0002",
                "score": 0.88,
            }
        ],
        "vector_results": [],
        "search_sources": ["wiki", "outputs"],
        "answer": "费曼技巧是一种通过教会别人来加深理解的学习方法。",
        "time_seconds": 0.42,
    }


class TestQueryEndpoint:
    """查询接口测试"""

    def test_query_basic(self, client) -> None:
        """基本查询"""
        with patch("dochris.api.routes.query.do_query") as mock_query:
            mock_query.return_value = _mock_query_result("费曼技巧")

            resp = client.get("/api/v1/query", params={"q": "费曼技巧"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "费曼技巧"
        assert len(data["concepts"]) == 1
        assert data["concepts"][0]["title"] == "费曼技巧"
        assert data["answer"] is not None
        assert data["time_seconds"] > 0

    def test_query_with_mode(self, client) -> None:
        """指定查询模式"""
        with patch("dochris.api.routes.query.do_query") as mock_query:
            mock_query.return_value = _mock_query_result(mode="concept")

            resp = client.get("/api/v1/query", params={"q": "学习", "mode": "concept"})

        assert resp.status_code == 200
        mock_query.assert_called_once_with(
            "学习", mode="concept", top_k=5, logger=mock_query.call_args[1]["logger"]
        )

    def test_query_with_top_k(self, client) -> None:
        """指定返回数量"""
        with patch("dochris.api.routes.query.do_query") as mock_query:
            mock_query.return_value = _mock_query_result()

            resp = client.get("/api/v1/query", params={"q": "测试", "top_k": 10})

        assert resp.status_code == 200
        call_kwargs = mock_query.call_args
        assert call_kwargs[1]["top_k"] == 10

    def test_query_missing_q(self, client) -> None:
        """缺少查询参数返回 422"""
        resp = client.get("/api/v1/query")
        assert resp.status_code == 422

    def test_query_empty_q(self, client) -> None:
        """空查询关键词返回 422"""
        resp = client.get("/api/v1/query", params={"q": ""})
        assert resp.status_code == 422

    def test_query_internal_error(self, client) -> None:
        """查询内部错误返回 500"""
        with patch("dochris.api.routes.query.do_query") as mock_query:
            mock_query.side_effect = RuntimeError("LLM 服务不可用")

            resp = client.get("/api/v1/query", params={"q": "测试"})

        assert resp.status_code == 500

    def test_query_no_results(self, client) -> None:
        """查询无结果"""
        with patch("dochris.api.routes.query.do_query") as mock_query:
            mock_query.return_value = {
                "query": "不存在的内容",
                "mode": "combined",
                "concepts": [],
                "summaries": [],
                "vector_results": [],
                "search_sources": [],
                "answer": None,
                "time_seconds": 0.1,
            }

            resp = client.get("/api/v1/query", params={"q": "不存在的内容"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["concepts"] == []
        assert data["answer"] is None
