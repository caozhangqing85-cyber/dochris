"""破坏性操作 preview/diff 测试（SEC-05）。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from dochris.api.app import create_app
from dochris.api.preview import file_change, preview_envelope

pytestmark = pytest.mark.fast


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    settings = type("S", (), {"workspace": str(tmp_path)})()
    app = create_app()
    with (
        patch("dochris.settings.get_settings", return_value=settings),
        patch("dochris.api.routes.promote.get_settings", return_value=settings),
        patch("dochris.api.routes.manifests.get_settings", return_value=settings),
        patch("dochris.api.routes.contribution.get_settings", return_value=settings),
        patch("dochris.api.app.get_settings", return_value=settings, create=True),
        TestClient(app) as test_client,
    ):
        test_client.workspace = tmp_path  # type: ignore[attr-defined]
        yield test_client


# ── preview 工具 ─────────────────────────────────────────────


def test_file_change_reports_create_overwrite_identical(tmp_path: Path) -> None:
    src = tmp_path / "src.md"
    src.write_text("内容A", encoding="utf-8")
    target_dir = tmp_path / "wiki"

    created = file_change(target_dir, src, workspace=tmp_path)
    assert created["action"] == "create"

    target_dir.mkdir()
    (target_dir / "src.md").write_text("内容A", encoding="utf-8")
    identical = file_change(target_dir, src, workspace=tmp_path)
    assert identical["action"] == "identical"

    (target_dir / "src.md").write_text("内容B更长的内容", encoding="utf-8")
    overwritten = file_change(target_dir, src, workspace=tmp_path)
    assert overwritten["action"] == "overwrite"
    assert overwritten["existing_size_bytes"] > overwritten["size_bytes"]


def test_preview_envelope_shape() -> None:
    envelope = preview_envelope("op", "summary", [{"a": 1}], ["blocker"])
    assert envelope == {
        "preview": True,
        "operation": "op",
        "summary": "summary",
        "changes": [{"a": 1}],
        "blockers": ["blocker"],
    }


# ── reset-failed preview ─────────────────────────────────────


def test_reset_failed_preview_does_not_mutate(client: TestClient, tmp_path: Path) -> None:
    failed = {
        "id": "SRC-0001",
        "title": "failed-doc",
        "status": "failed",
        "type": "other",
        "file_path": "raw/failed-doc.md",
    }
    ok = {
        "id": "SRC-0002",
        "title": "ok-doc",
        "status": "ingested",
        "type": "other",
        "file_path": "raw/ok-doc.md",
    }

    def _fake_manifests(_workspace: str, status: str | None = None) -> list[dict]:
        all_manifests = [failed, ok]
        return [m for m in all_manifests if status is None or m["status"] == status]

    with (
        patch("dochris.api.routes.manifests.get_all_manifests", side_effect=_fake_manifests),
        patch("dochris.manifest.update_manifest_status") as mock_update,
    ):
        resp = client.post("/api/v1/manifests/reset-failed?preview=true")

    assert resp.status_code == 200
    data = resp.json()
    assert data["preview"] is True
    assert data["operation"] == "reset_failed"
    assert data["changes"] == [
        {"id": "SRC-0001", "title": "failed-doc", "from_status": "failed", "to_status": "ingested"}
    ]
    mock_update.assert_not_called()


def test_reset_failed_preview_honors_manifest_status_filter(
    client: TestClient,
) -> None:
    with (
        patch(
            "dochris.api.routes.manifests.get_all_manifests",
            return_value=[{"id": "SRC-0009", "title": "t", "status": "compile_failed"}],
        ),
        patch("dochris.manifest.update_manifest_status") as mock_update,
    ):
        resp = client.post("/api/v1/manifests/reset-failed?preview=true")

    data = resp.json()
    assert data["changes"][0]["from_status"] == "compile_failed"
    mock_update.assert_not_called()


# ── promote preview ──────────────────────────────────────────


def _make_workspace_with_compiled_doc(ws: Path) -> None:
    """构造 compiled 文档 + outputs/wiki 文件布局。"""
    manifest = {
        "id": "SRC-0001",
        "title": "示例文档",
        "status": "compiled",
        "compiled_summary": {
            "concepts": [{"name": "软着陆"}],
            "one_line": "测试",
        },
    }
    (ws / "manifests" / "sources").mkdir(parents=True, exist_ok=True)
    (ws / "manifests" / "sources" / "SRC-0001.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    (ws / "outputs" / "summaries").mkdir(parents=True, exist_ok=True)
    (ws / "outputs" / "summaries" / "示例文档.md").write_text("摘要", encoding="utf-8")
    (ws / "outputs" / "concepts").mkdir(parents=True, exist_ok=True)
    (ws / "outputs" / "concepts" / "软着陆.md").write_text("概念", encoding="utf-8")


def test_promote_preview_lists_planned_files(client: TestClient, tmp_path: Path) -> None:
    _make_workspace_with_compiled_doc(tmp_path)

    with patch(
        "dochris.api.routes.promote.quality_gate",
        return_value={"passed": True, "reason": "ok"},
    ):
        resp = client.post("/api/v1/promote/SRC-0001/preview", json={"target": "wiki"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["preview"] is True
    assert data["blockers"] == []
    paths = {change["path"] for change in data["changes"]}
    assert any("wiki/summaries" in p for p in paths)
    assert any("wiki/concepts" in p for p in paths)
    assert all(change["action"] == "create" for change in data["changes"])


def test_promote_preview_reports_status_blocker_without_files(
    client: TestClient,
    tmp_path: Path,
) -> None:
    manifest = {"id": "SRC-0002", "title": "x", "status": "ingested"}
    (tmp_path / "manifests" / "sources").mkdir(parents=True, exist_ok=True)
    (tmp_path / "manifests" / "sources" / "SRC-0002.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    resp = client.post("/api/v1/promote/SRC-0002/preview", json={"target": "wiki"})

    data = resp.json()
    assert data["changes"] == []
    assert any("状态" in blocker for blocker in data["blockers"])


def test_promote_preview_detects_overwrite(client: TestClient, tmp_path: Path) -> None:
    _make_workspace_with_compiled_doc(tmp_path)
    (tmp_path / "wiki" / "summaries").mkdir(parents=True, exist_ok=True)
    (tmp_path / "wiki" / "summaries" / "示例文档.md").write_text(
        "旧版本内容不一样", encoding="utf-8"
    )

    with patch(
        "dochris.api.routes.promote.quality_gate",
        return_value={"passed": True, "reason": "ok"},
    ):
        resp = client.post("/api/v1/promote/SRC-0001/preview", json={"target": "wiki"})

    data = resp.json()
    summary_change = next((c for c in data["changes"] if "summaries" in c["path"]), None)
    assert summary_change is not None
    assert summary_change["action"] == "overwrite"
    assert summary_change["existing_size_bytes"] != summary_change["size_bytes"]


def test_promote_preview_404_for_unknown_manifest(client: TestClient) -> None:
    resp = client.post("/api/v1/promote/SRC-9999/preview", json={"target": "wiki"})
    assert resp.status_code == 404


# ── discard preview ──────────────────────────────────────────


def test_discard_preview_returns_candidate_without_mutating(
    client: TestClient,
    tmp_path: Path,
) -> None:
    meta_dir = tmp_path / "outputs" / "candidates" / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.joinpath("QRY-abc.json").write_text(
        json.dumps(
            {"id": "QRY-abc", "query": "什么是软着陆", "status": "candidate", "quality_score": 88}
        ),
        encoding="utf-8",
    )

    with patch("dochris.quality.query_contribution.discard_candidate") as mock_discard:
        resp = client.post("/api/v1/candidates/QRY-abc/discard?preview=true")

    assert resp.status_code == 200
    data = resp.json()
    assert data["preview"] is True
    assert data["changes"][0]["id"] == "QRY-abc"
    assert data["changes"][0]["to_status"] == "discarded"
    mock_discard.assert_not_called()


def test_discard_preview_404_for_unknown_candidate(client: TestClient) -> None:
    resp = client.post("/api/v1/candidates/QRY-nope/discard?preview=true")
    assert resp.status_code == 404
