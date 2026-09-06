"""Compile API 幂等重放契约测试（review P0/P1 回归）。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from dochris.api.app import create_app
from dochris.api.job_repository import SQLiteJobRepository

pytestmark = pytest.mark.fast


def _client(tmp_path: Path):
    settings = SimpleNamespace(workspace=str(tmp_path))
    repo = SQLiteJobRepository(tmp_path / "data" / "jobs.db")
    app = create_app()
    patches = [
        patch("dochris.api.routes.compile.get_default_workspace", return_value=str(tmp_path)),
        patch("dochris.api.routes.compile.build_repository", return_value=(repo, "sqlite")),
        patch("dochris.phases.phase2_compilation.get_all_manifests", return_value=[]),
        patch("dochris.api.app.get_settings", return_value=settings, create=True),
    ]
    client = TestClient(app)
    for p in patches:
        p.start()
    return client, repo, patches


def _stop(patches) -> None:
    for p in patches:
        p.stop()


def _seed_completed(repo, job_id: str, key: str) -> None:
    repo.save(
        {
            "job_id": job_id,
            "status": "completed",
            "total": 3,
            "processed": 3,
            "compiled": 3,
            "failed": 0,
            "current_files": [],
            "idempotency_key": key,
            "message": "编译完成",
            "created_at": "2026-09-06T00:00:00+00:00",
        }
    )


def _make_manifest_patch(manifests):
    return patch(
        "dochris.api.routes.compile.get_all_manifests",
        return_value=manifests,
    )


def test_replay_completed_key_with_pending_returns_original_job(tmp_path: Path) -> None:
    """旧任务已完成 + 存在 pending + 重放旧 key → 原样返回旧任务（非 accepted）。"""
    client, repo, patches = _client(tmp_path)
    _seed_completed(repo, "job-old", "key-old")
    manifests = [{"id": "SRC-0001", "status": "ingested"}]

    try:
        with _make_manifest_patch(manifests) as _:
            resp = client.post(
                "/api/v1/compile",
                json={"concurrency": 1},
                headers={"Idempotency-Key": "key-old"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == "job-old"
        assert data["status"] == "completed", f"重放必须返回原始状态，得到 {data['status']}"
        assert data["message"] == "编译完成"
    finally:
        _stop(patches)


def test_replay_completed_key_without_pending_returns_original_job(tmp_path: Path) -> None:
    """重放 key 且无 pending 文档：必须返回旧任务，而不是 no_work。"""
    client, repo, patches = _client(tmp_path)
    _seed_completed(repo, "job-old", "key-old")

    try:
        with patch(
            "dochris.api.routes.compile.get_all_manifests",
            return_value=[],
        ):
            resp = client.post(
                "/api/v1/compile",
                json={"concurrency": 1},
                headers={"Idempotency-Key": "key-old"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == "job-old"
        assert data["status"] == "completed"
        assert data["message"] != "没有待编译的文档"
    finally:
        _stop(patches)


def test_replay_key_with_unrelated_active_job_returns_original(tmp_path: Path) -> None:
    """旧任务已完成 + 无关任务运行中 + 重放旧 key → 返回旧任务而非运行中任务。"""
    client, repo, patches = _client(tmp_path)
    _seed_completed(repo, "job-old", "key-old")
    # 预置一个无关的运行中任务（无幂等键）
    repo.save(
        {
            "job_id": "job-running",
            "status": "running",
            "total": 5,
            "processed": 1,
            "compiled": 1,
            "failed": 0,
            "current_files": ["SRC-0009"],
            "idempotency_key": None,
            "lease_owner": "worker-x",
            "lease_expires_at": "2099-01-01T00:00:00+00:00",
            "message": "编译进行中",
            "created_at": "2026-09-06T00:00:00+00:00",
        }
    )

    try:
        with patch(
            "dochris.api.routes.compile.get_all_manifests",
            return_value=[{"id": "SRC-0001", "status": "ingested"}],
        ):
            resp = client.post(
                "/api/v1/compile",
                json={"concurrency": 1},
                headers={"Idempotency-Key": "key-old"},
            )

        data = resp.json()
        assert data["job_id"] == "job-old", f"重放必须返回旧任务，得到 {data['job_id']}"
        assert data["status"] == "completed"
    finally:
        _stop(patches)


def test_new_key_while_unrelated_active_returns_active_job(tmp_path: Path) -> None:
    """新 key（无重放）+ 无关任务运行中 → 返回运行中任务（互斥语义保留）。"""
    client, repo, patches = _client(tmp_path)
    repo.save(
        {
            "job_id": "job-running",
            "status": "running",
            "total": 5,
            "processed": 1,
            "compiled": 1,
            "failed": 0,
            "current_files": ["SRC-0009"],
            "idempotency_key": None,
            "lease_owner": "worker-x",
            "lease_expires_at": "2099-01-01T00:00:00+00:00",
            "message": "编译进行中",
            "created_at": "2026-09-06T00:00:00+00:00",
        }
    )

    try:
        with patch(
            "dochris.api.routes.compile.get_all_manifests",
            return_value=[{"id": "SRC-0001", "status": "ingested"}],
        ):
            resp = client.post(
                "/api/v1/compile",
                json={"concurrency": 1},
                headers={"Idempotency-Key": "brand-new-key"},
            )

        data = resp.json()
        assert data["job_id"] == "job-running"
        assert data["status"] == "running"
    finally:
        _stop(patches)
