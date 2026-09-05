"""Manifest API 合同测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.fast


def test_list_manifests_preserves_quality_metadata(client, tmp_workspace) -> None:
    """编译阶段产生的 provenance/lint 必须原样交给质量与编译页面。"""
    manifest = {
        "id": "SRC-0001",
        "title": "质量合同",
        "type": "markdown",
        "status": "compiled",
        "compiled_summary": {
            "one_line": "摘要",
            "key_points": ["要点"],
            "detailed_summary": "详细摘要",
            "concepts": ["合同测试"],
            "quality_score": 92,
            "provenance": {
                "overall_label": "extracted",
                "signals": {"quote_coverage": 0.8},
            },
            "lint": {
                "passed": True,
                "score": 0.95,
                "issues": [],
            },
        },
    }

    with (
        patch(
            "dochris.api.routes.manifests.get_settings",
            return_value=SimpleNamespace(workspace=tmp_workspace),
        ),
        patch(
            "dochris.api.routes.manifests.get_all_manifests",
            return_value=[manifest],
        ),
    ):
        response = client.get("/api/v1/manifests")

    assert response.status_code == 200
    compiled_summary = response.json()[0]["compiled_summary"]
    assert compiled_summary["provenance"] == manifest["compiled_summary"]["provenance"]
    assert compiled_summary["lint"] == manifest["compiled_summary"]["lint"]
