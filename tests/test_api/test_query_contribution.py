"""显式 Query-as-Contribution 写接口契约测试。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from dochris.api.app import create_app
from dochris.quality.query_contribution import auto_contribute_from_query

pytestmark = pytest.mark.fast


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _payload(answer: str | None = None) -> dict[str, object]:
    return {
        "query": "如何使用费曼技巧？",
        "mode": "combined",
        "concepts": [
            {
                "title": "费曼技巧",
                "content": "通过解释来检验理解",
                "source": "wiki",
                "manifest_id": "SRC-0001",
                "score": 0.95,
            }
        ],
        "summaries": [],
        "vector_results": [],
        "search_sources": ["wiki"],
        "answer": answer or ("这是一个足够长的知识回答。" * 12),
        "time_seconds": 0.42,
    }


def test_post_query_contribution_persists_explicit_payload(
    client: TestClient,
    tmp_path: Path,
) -> None:
    contribution = {
        "id": "QRY-20260830-abcdef",
        "quality_score": 88,
        "needs_review": True,
        "auto_promoted": False,
        "status": "candidate",
    }
    with (
        patch(
            "dochris.api.routes.contribution.get_settings",
            return_value=SimpleNamespace(workspace=tmp_path),
        ),
        patch(
            "dochris.api.routes.contribution.auto_contribute_from_query",
            return_value=contribution,
        ) as mock_contribute,
    ):
        response = client.post("/api/v1/query/contribution", json=_payload())

    assert response.status_code == 201
    assert response.json() == contribution
    mock_contribute.assert_called_once()
    assert mock_contribute.call_args.kwargs["workspace_path"] == tmp_path
    query_result = mock_contribute.call_args.kwargs["query_result"]
    assert query_result["query"] == "如何使用费曼技巧？"
    assert query_result["answer"].startswith("这是一个足够长的知识回答")
    assert query_result["concepts"][0]["manifest_id"] == "SRC-0001"


def test_post_query_contribution_rejects_short_answers(client: TestClient) -> None:
    response = client.post(
        "/api/v1/query/contribution",
        json=_payload(answer="太短"),
    )

    assert response.status_code == 422


def test_auto_contribution_normalizes_api_concept_shape(tmp_path: Path) -> None:
    with patch(
        "dochris.quality.query_contribution.contribute_query_result",
        return_value={"id": "QRY-1", "quality_score": 88},
    ) as mock_contribute:
        result = auto_contribute_from_query(tmp_path, _payload())

    assert result == {"id": "QRY-1", "quality_score": 88}
    concepts = mock_contribute.call_args.kwargs["concepts"]
    assert concepts == [
        {
            "title": "费曼技巧",
            "content": "通过解释来检验理解",
            "source": "wiki",
            "manifest_id": "SRC-0001",
            "score": 0.95,
            "name": "费曼技巧",
            "explanation": "通过解释来检验理解",
        }
    ]
