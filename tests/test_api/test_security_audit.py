"""安全审计与配置保护测试（SEC-03/SEC-04）。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from dochris.api.app import create_app
from dochris.api.audit import new_operation_id, workspace_rewrite_allowed

pytestmark = pytest.mark.fast


def test_operation_id_is_unique() -> None:
    assert new_operation_id() != new_operation_id()


def test_workspace_rewrite_rules() -> None:
    """local-only 允许、受保护部署默认禁止、显式放行覆盖。"""
    with patch.dict("os.environ", {}, clear=True):
        assert workspace_rewrite_allowed() is True  # local-only

    with patch.dict("os.environ", {"DOCHRIS_API_KEY": "secret"}, clear=True):
        assert workspace_rewrite_allowed() is False

    with patch.dict(
        "os.environ",
        {"DOCHRIS_API_KEY": "secret", "DOCHRIS_ALLOW_WORKSPACE_REWRITE": "true"},
        clear=True,
    ):
        assert workspace_rewrite_allowed() is True

    with patch.dict(
        "os.environ",
        {"DOCHRIS_ALLOW_WORKSPACE_REWRITE": "false"},
        clear=True,
    ):
        assert workspace_rewrite_allowed() is False


def test_write_requests_are_audited(tmp_path: Path) -> None:
    """非 GET 请求必须产生带 operation id 的审计事件与响应头。"""
    audit_log = tmp_path / "logs" / "audit.log"
    settings = SimpleNamespace(workspace=str(tmp_path))
    app = create_app()

    with (
        patch("dochris.api.audit._audit_log_path", return_value=audit_log),
        patch("dochris.api.app.get_settings", return_value=settings, create=True),
        # 后台 runner 钉住为空，避免测试触碰真实工作区
        patch("dochris.phases.phase2_compilation.get_all_manifests", return_value=[]),
        TestClient(app) as client,
    ):
        resp = client.post("/api/v1/compile", json={"limit": 1, "concurrency": 1})

    assert resp.status_code == 200
    operation_id = resp.headers.get("X-Operation-ID")
    assert operation_id

    lines = audit_log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    event = __import__("json").loads(lines[0])
    assert event["operation_id"] == operation_id
    assert event["method"] == "POST"
    assert event["path"] == "/api/v1/compile"
    assert event["idempotency_key"] == ""


def test_idempotency_key_is_recorded(tmp_path: Path) -> None:
    """客户端 Idempotency-Key 必须原样进入审计事件。"""
    audit_log = tmp_path / "logs" / "audit.log"
    settings = SimpleNamespace(workspace=str(tmp_path))
    app = create_app()

    with (
        patch("dochris.api.audit._audit_log_path", return_value=audit_log),
        patch("dochris.api.app.get_settings", return_value=settings, create=True),
        patch("dochris.phases.phase2_compilation.get_all_manifests", return_value=[]),
        TestClient(app) as client,
    ):
        client.post(
            "/api/v1/compile",
            json={"limit": 1, "concurrency": 1},
            headers={"Idempotency-Key": "op-123"},
        )

    lines = audit_log.read_text(encoding="utf-8").strip().splitlines()
    event = __import__("json").loads(lines[-1])
    assert event["idempotency_key"] == "op-123"


def test_protected_deployment_cannot_rewrite_workspace(tmp_path: Path) -> None:
    """SEC-03：配置 API key 的部署拒绝运行时改写 workspace。"""
    app = create_app()
    with (
        patch.dict(
            "os.environ",
            {"DOCHRIS_API_KEY": "secret", "DOCHRIS_ALLOW_UNAUTHENTICATED": "true"},
            clear=False,
        ),
        patch.dict("os.environ", {"DOCHRIS_ALLOW_WORKSPACE_REWRITE": "false"}, clear=False),
        TestClient(app) as client,
    ):
        resp = client.put(
            "/api/v1/config",
            json={"workspace": "/tmp/evil-workspace"},
            headers={"X-API-Key": "secret"},
        )

    assert resp.status_code == 403
    assert "DOCHRIS_ALLOW_WORKSPACE_REWRITE" in resp.json()["detail"]


def test_local_only_mode_can_rewrite_workspace(tmp_path: Path) -> None:
    """SEC-03：local-only 模式保留原有体验，可改写 workspace。"""
    app = create_app()
    env = {
        "DOCHRIS_API_KEY": "",
        "DOCHRIS_ALLOW_UNAUTHENTICATED": "true",
        "WORKSPACE": str(tmp_path),
    }
    with patch.dict("os.environ", env, clear=False):
        with TestClient(app) as client:
            resp = client.put("/api/v1/config", json={"workspace": str(tmp_path)})

    assert resp.status_code == 200
    assert resp.json()["workspace"] == str(tmp_path)
