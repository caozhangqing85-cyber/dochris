"""上传持久化与审计盲区修复测试（review 高/中风险项）。"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from dochris.api.app import create_app

pytestmark = pytest.mark.fast


def _settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        workspace=tmp_path,
        raw_dir=tmp_path / "raw",
        max_file_size=100 * 1024 * 1024,
    )


def _client(tmp_path: Path):
    settings = _settings(tmp_path)
    patches = [
        patch("dochris.settings.get_settings", return_value=settings),
        patch("dochris.api.routes.files.get_settings", return_value=settings),
        patch("dochris.api.app.get_settings", return_value=settings, create=True),
    ]
    client = TestClient(create_app())
    for p in patches:
        p.start()
    return client, patches


def _stop(patches) -> None:
    for p in patches:
        p.stop()


def test_upload_entity_lives_in_raw_and_inbox_holds_link(tmp_path: Path) -> None:
    """上传实体必须落在持久卷 raw/；uploads/inbox 只保留反向软链。"""
    client, patches = _client(tmp_path)
    try:
        with client:
            resp = client.post(
                "/api/v1/files/upload",
                files={"files": ("持久化笔记.md", "正文" * 20, "text/markdown")},
            )
        assert resp.status_code == 200
        assert resp.json()["saved"] == 1

        raw_files = list((tmp_path / "raw" / "articles").glob("*.md"))
        assert len(raw_files) == 1
        entity = raw_files[0]
        assert entity.is_file() and not entity.is_symlink(), "实体必须在 raw（持久卷）内"

        inbox_link = tmp_path / "uploads" / "inbox" / entity.name
        assert inbox_link.is_symlink(), "inbox 应为指向 raw 的软链"
        assert entity.read_text(encoding="utf-8") == "正文" * 20

        manifest = json.loads(
            (tmp_path / "manifests" / "sources" / "SRC-0001.json").read_text(encoding="utf-8")
        )
        assert manifest["file_path"].startswith("raw/")
        assert (
            str(entity) == manifest["source_path"]
            or Path(manifest["source_path"]) == entity.resolve()
        )
    finally:
        _stop(patches)


def test_upload_without_multipart_returns_400(tmp_path: Path) -> None:
    """File(None) + len(None) 曾导致 500；空上传是请求级错误，必须 4xx。"""
    client, patches = _client(tmp_path)
    try:
        with client:
            resp = client.post("/api/v1/files/upload")
        assert resp.status_code == 400
        assert "未收到任何文件" in resp.json()["error"]
    finally:
        _stop(patches)


def test_upload_too_many_files_returns_413(tmp_path: Path) -> None:
    files = [("files", (f"f{i}.md", b"xxxxxxxxxx", "text/markdown")) for i in range(51)]
    client, patches = _client(tmp_path)
    try:
        with client:
            resp = client.post("/api/v1/files/upload", files=files)
        assert resp.status_code == 413
        assert "最多上传" in resp.json()["error"]
    finally:
        _stop(patches)


def test_unhandled_write_exception_still_audited(tmp_path: Path) -> None:
    """审计盲区修复：处理请求时抛出的未捕获异常也要写入审计日志。"""
    audit_log = tmp_path / "logs" / "audit.log"
    settings = _settings(tmp_path)
    app = create_app()

    with (
        patch("dochris.api.audit._audit_log_path", return_value=audit_log),
        patch("dochris.api.app.get_settings", return_value=settings, create=True),
        patch("dochris.api.routes.files.get_settings", return_value=settings),
        # 在路由 try 块之外抛出（get_all_manifests 位于循环前），
        # 构造真正未处理的异常以验证审计中间件的 except 分支
        patch(
            "dochris.api.routes.files.get_all_manifests",
            side_effect=RuntimeError("boom"),
        ),
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        resp = client.post(
            "/api/v1/files/upload",
            files={"files": ("x.md", "内容", "text/markdown")},
        )

    assert resp.status_code == 500
    lines = audit_log.read_text(encoding="utf-8").strip().splitlines()
    event = json.loads(lines[-1])
    assert event["method"] == "POST"
    assert event["path"] == "/api/v1/files/upload"
    assert event["status_code"] == 500
