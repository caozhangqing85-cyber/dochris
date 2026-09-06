"""候选详情端点测试（UX-03：全文/来源/冲突/晋升 diff 计划）。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from dochris.api.app import create_app

pytestmark = pytest.mark.fast


def _seed_candidate(ws: Path, *, status: str = "candidate") -> None:
    meta_dir = ws / "outputs" / "candidates" / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    (ws / "outputs" / "candidates").mkdir(parents=True, exist_ok=True)
    content = ws / "outputs" / "candidates" / "查询衍生-软着陆.md"
    content.write_text("# 查询衍生: 软着陆\n\n软着陆指价格缓慢回归。", encoding="utf-8")
    meta = {
        "id": "QRY-20260906-abc123",
        "title": "查询衍生: 软着陆",
        "status": status,
        "query": "什么是软着陆",
        "quality_score": 90,
        "content_hash": "deadbeefcafe",
        "needs_review": False,
        "contradiction": {
            "has_contradiction": True,
            "conflicts": [{"summary": "与 wiki/summaries/房价.md 冲突"}],
        },
        "source_manifest_ids": ["SRC-0001", "SRC-0003"],
        "concepts_extracted": [{"name": "软着陆", "explanation": "价格缓慢回归"}],
        "file": str(content.relative_to(ws)),
    }
    meta_dir.joinpath("QRY-20260906-abc123.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )


def test_candidate_detail_returns_full_text_sources_and_plan(tmp_path: Path) -> None:
    _seed_candidate(tmp_path)
    settings = type("S", (), {"workspace": str(tmp_path)})()
    app = create_app()

    with (
        patch("dochris.settings.get_settings", return_value=settings),
        patch("dochris.api.routes.contribution.get_settings", return_value=settings),
        patch("dochris.api.app.get_settings", return_value=settings, create=True),
        TestClient(app) as client,
    ):
        resp = client.get("/api/v1/candidates/QRY-20260906-abc123")

    assert resp.status_code == 200
    data = resp.json()

    assert "软着陆指价格缓慢回归" in data["full_text"]
    assert data["source_manifest_ids"] == ["SRC-0001", "SRC-0003"]
    assert data["contradiction"]["has_contradiction"] is True

    plan = data["promote_plan"]
    assert plan["blockers"] == []
    actions = {change["path"]: change["action"] for change in plan["changes"]}
    summary_path = next(p for p in actions if "wiki/summaries" in p)
    assert actions[summary_path] == "create"
    concept_path = next(p for p in actions if "wiki/concepts" in p)
    assert actions[concept_path] == "create"


def test_candidate_detail_promote_plan_avoids_overwrite_via_suffix(tmp_path: Path) -> None:
    """与 promote_candidate 一致：同名 wiki 文件已存在时改用哈希后缀，不覆盖。"""
    _seed_candidate(tmp_path)
    wiki_dir = tmp_path / "wiki" / "summaries"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    (wiki_dir / "查询衍生-软着陆.md").write_text("旧的 wiki 版本，内容不同", encoding="utf-8")

    settings = type("S", (), {"workspace": str(tmp_path)})()
    app = create_app()

    with (
        patch("dochris.settings.get_settings", return_value=settings),
        patch("dochris.api.routes.contribution.get_settings", return_value=settings),
        patch("dochris.api.app.get_settings", return_value=settings, create=True),
        TestClient(app) as client,
    ):
        resp = client.get("/api/v1/candidates/QRY-20260906-abc123")

    plan = resp.json()["promote_plan"]
    summary_change = next(c for c in plan["changes"] if "wiki/summaries" in c["path"])
    assert summary_change["action"] == "create"
    assert "_dead" in summary_change["path"]  # 计划路径使用 content_hash 前 4 位后缀，避开已有文件


def test_candidate_detail_promote_plan_identical_for_same_content(tmp_path: Path) -> None:
    """目标已存在且内容字节相同时计划为 identical（幂等重放）。"""
    _seed_candidate(tmp_path)
    wiki_dir = tmp_path / "wiki" / "summaries"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    content = tmp_path / "outputs" / "candidates" / "查询衍生-软着陆.md"
    (wiki_dir / "查询衍生-软着陆.md").write_bytes(content.read_bytes())
    # 基名被占用时 promote 会改用哈希后缀；后缀同名且字节相同 → identical
    (wiki_dir / "查询衍生-软着陆_dead.md").write_bytes(content.read_bytes())

    settings = type("S", (), {"workspace": str(tmp_path)})()
    app = create_app()

    with (
        patch("dochris.settings.get_settings", return_value=settings),
        patch("dochris.api.routes.contribution.get_settings", return_value=settings),
        patch("dochris.api.app.get_settings", return_value=settings, create=True),
        TestClient(app) as client,
    ):
        resp = client.get("/api/v1/candidates/QRY-20260906-abc123")

    plan = resp.json()["promote_plan"]
    summary_change = next(c for c in plan["changes"] if "wiki/summaries" in c["path"])
    assert summary_change["action"] == "identical"


def test_candidate_detail_404_for_unknown(tmp_path: Path) -> None:
    settings = type("S", (), {"workspace": str(tmp_path)})()
    app = create_app()

    with (
        patch("dochris.settings.get_settings", return_value=settings),
        patch("dochris.api.routes.contribution.get_settings", return_value=settings),
        patch("dochris.api.app.get_settings", return_value=settings, create=True),
        TestClient(app) as client,
    ):
        resp = client.get("/api/v1/candidates/QRY-missing")

    assert resp.status_code == 404
