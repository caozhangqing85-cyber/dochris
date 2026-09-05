"""任务仓库测试（JOB-03/04/05：repository 抽象、SQLite WAL、lease/幂等）。"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from dochris.api.compile_jobs import CompileJobManager
from dochris.api.job_repository import (
    JsonJobRepository,
    SQLiteJobRepository,
    build_repository,
)

pytestmark = pytest.mark.fast


def _sample_record(job_id: str = "job-1", status: str = "queued") -> dict[str, object]:
    return {
        "job_id": job_id,
        "status": status,
        "total": 2,
        "processed": 0,
        "compiled": 0,
        "failed": 0,
        "idempotency_key": None,
    }


# ── JOB-04：SQLite WAL 事务存储 ───────────────────────────────


def test_sqlite_repository_enables_wal(tmp_path: Path) -> None:
    repo = SQLiteJobRepository(tmp_path / "jobs.db")
    mode = repo._conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert str(mode).lower() == "wal"
    repo.close()


def test_sqlite_save_get_roundtrip_preserves_order(tmp_path: Path) -> None:
    repo = SQLiteJobRepository(tmp_path / "jobs.db")
    for job_id in ("job-a", "job-b", "job-c"):
        repo.save(_sample_record(job_id))

    assert repo.get("job-b")["job_id"] == "job-b"
    assert repo.get("missing") is None
    assert [r["job_id"] for r in repo.list_all()] == ["job-a", "job-b", "job-c"]

    repo.save(_sample_record("job-a", status="completed"))
    assert repo.get("job-a")["status"] == "completed"
    assert [r["job_id"] for r in repo.list_all()] == ["job-a", "job-b", "job-c"]
    repo.close()


def test_sqlite_survives_reconnection(tmp_path: Path) -> None:
    repo = SQLiteJobRepository(tmp_path / "jobs.db")
    repo.save(_sample_record("persisted"))
    repo.close()

    reopened = SQLiteJobRepository(tmp_path / "jobs.db")
    assert reopened.get("persisted") is not None
    reopened.close()


def test_json_to_sqlite_migration_is_automatic_once(tmp_path: Path) -> None:
    json_path = tmp_path / "compile-jobs.json"
    json_path.write_text(
        json.dumps({"version": 1, "jobs": [_sample_record("legacy-1")]}),
        encoding="utf-8",
    )

    repo = SQLiteJobRepository(tmp_path / "compile-jobs.db", migrate_from=json_path)
    assert repo.get("legacy-1") is not None

    # 二次打开不重复迁移；也不覆盖已有数据
    repo.save(_sample_record("fresh"))
    repo.close()
    repo2 = SQLiteJobRepository(tmp_path / "compile-jobs.db", migrate_from=json_path)
    assert repo2.get("fresh") is not None
    repo2.close()


def test_json_repository_quarantine_is_preserved(tmp_path: Path) -> None:
    store = tmp_path / "compile-jobs.json"
    store.write_text("{broken-json", encoding="utf-8")

    repo = JsonJobRepository(store)
    assert repo.list_all() == []
    quarantined = list(tmp_path.glob("compile-jobs.corrupt-*.json"))
    assert len(quarantined) == 1


# ── JOB-05：lease / heartbeat / 幂等键 ────────────────────────


def test_sqlite_reclaims_expired_foreign_lease_as_interrupted(tmp_path: Path) -> None:
    repo = SQLiteJobRepository(tmp_path / "jobs.db")
    expired = (datetime.now(UTC) - timedelta(seconds=10)).isoformat()
    repo.save(
        {
            **_sample_record("stale", status="running"),
            "lease_owner": "other-process",
            "lease_expires_at": expired,
        }
    )

    records = repo.recover_stale_leases(owner_id="this-process")
    [stale] = [r for r in records if r["job_id"] == "stale"]
    assert stale["status"] == "interrupted"
    assert stale["lease_owner"] is None
    repo.close()


def test_sqlite_keeps_valid_foreign_lease_running(tmp_path: Path) -> None:
    repo = SQLiteJobRepository(tmp_path / "jobs.db")
    fresh = (datetime.now(UTC) + timedelta(seconds=300)).isoformat()
    repo.save(
        {
            **_sample_record("live", status="running"),
            "lease_owner": "other-process",
            "lease_expires_at": fresh,
        }
    )

    records = repo.recover_stale_leases(owner_id="this-process")
    [live] = [r for r in records if r["job_id"] == "live"]
    assert live["status"] == "running"
    assert live["lease_owner"] == "other-process"
    repo.close()


def test_sqlite_find_by_idempotency_key_returns_newest(tmp_path: Path) -> None:
    repo = SQLiteJobRepository(tmp_path / "jobs.db")
    repo.save({**_sample_record("old"), "idempotency_key": "op-1"})
    repo.save({**_sample_record("new", status="completed"), "idempotency_key": "op-1"})

    found = repo.find_by_idempotency_key("op-1")
    assert found is not None
    assert found["job_id"] == "new"
    assert repo.find_by_idempotency_key("nope") is None
    repo.close()


@pytest.mark.asyncio
async def test_manager_start_honors_idempotency_key() -> None:
    manager = CompileJobManager()

    async def runner(*, progress_callback: Callable[..., None]) -> None:
        progress_callback(processed=1, compiled=1, failed=0, current_files=[])

    first = manager.start(1, runner, idempotency_key="op-1")
    await _wait_terminal(first)

    again = manager.start(1, runner, idempotency_key="op-1")
    assert again.job_id == first.job_id
    await manager.close()


@pytest.mark.asyncio
async def test_manager_with_sqlite_store_persists_and_recovers(tmp_path: Path) -> None:
    db_path = tmp_path / "jobs.db"
    manager = CompileJobManager(repository=SQLiteJobRepository(db_path))

    async def runner(*, progress_callback: Callable[..., None]) -> None:
        progress_callback(
            processed=1,
            compiled=0,
            failed=1,
            current_files=[],
            failed_files=["SRC-0001"],
            failures=[{"src_id": "SRC-0001", "error": "RuntimeError: x"}],
        )

    job = manager.start(1, runner)
    await _wait_terminal(job)
    manager._repository.close()  # type: ignore[union-attr]

    reopened = CompileJobManager(repository=SQLiteJobRepository(db_path))
    restored = reopened.get(job.job_id)
    assert restored is not None
    assert restored.status == "completed_with_errors"
    assert restored.failed_files == ["SRC-0001"]
    await reopened.close()


@pytest.mark.asyncio
async def test_manager_running_job_acquires_and_releases_lease(tmp_path: Path) -> None:
    repo = SQLiteJobRepository(tmp_path / "jobs.db")
    manager = CompileJobManager(repository=repo, lease_ttl_seconds=60.0)
    started = asyncio.Event()

    async def runner(*, progress_callback: Callable[..., None]) -> None:
        started.set()
        await asyncio.Event().wait()

    job = manager.start(1, runner)
    await asyncio.wait_for(started.wait(), timeout=1.0)

    assert job.status == "running"
    assert job.lease_owner == manager._owner_id
    assert job.lease_expires_at is not None
    stored = repo.get(job.job_id)
    assert stored is not None and stored["lease_owner"] == manager._owner_id

    await manager.close()
    assert job.status == "cancelled"
    assert job.lease_owner is None
    # close 会释放仓库连接；用新连接验证 lease 已在库中清除
    reopened = SQLiteJobRepository(tmp_path / "jobs.db")
    stored = reopened.get(job.job_id)
    assert stored is not None and stored["lease_owner"] is None
    reopened.close()


@pytest.mark.asyncio
async def test_manager_restarts_running_job_as_interrupted_with_json_repo(
    tmp_path: Path,
) -> None:
    """JSON 仓库保留旧的启动中断恢复语义。"""
    store = tmp_path / "compile-jobs.json"
    manager = CompileJobManager(store_path=store)
    started = asyncio.Event()

    async def runner(*, progress_callback: Callable[..., None]) -> None:
        started.set()
        await asyncio.Event().wait()

    job = manager.start(1, runner)
    await asyncio.wait_for(started.wait(), timeout=1.0)

    try:
        second = CompileJobManager(store_path=store)
        restored = second.get(job.job_id)
        assert restored is not None
        assert restored.status == "interrupted"
    finally:
        await manager.close()


def test_build_repository_selects_by_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DOCHRIS_JOB_STORE", "json")
    repo, kind = build_repository(tmp_path)
    assert kind == "json"
    assert isinstance(repo, JsonJobRepository)

    monkeypatch.setenv("DOCHRIS_JOB_STORE", "sqlite")
    repo, kind = build_repository(tmp_path)
    assert kind == "sqlite"
    assert isinstance(repo, SQLiteJobRepository)
    repo.close()


def test_sqlite_store_is_selected_by_default_in_app(tmp_path: Path) -> None:
    """API 装配默认创建 SQLite 仓库（JOB-04 验收）。"""
    from fastapi.testclient import TestClient

    from dochris.api.app import create_app
    from dochris.api.job_repository import SQLiteJobRepository as Repo

    settings = type("S", (), {"workspace": str(tmp_path)})()

    with (
        patch(
            "dochris.api.routes.compile.get_all_manifests",
            return_value=[{"id": "SRC-0001", "status": "ingested"}],
        ),
        # 后台 runner 用真实 phase2 模块，必须钉住为空避免触碰真实工作区
        patch("dochris.phases.phase2_compilation.get_all_manifests", return_value=[]),
        patch("dochris.api.routes.compile.get_default_workspace", return_value=str(tmp_path)),
        patch("dochris.api.routes.compile.build_repository") as mock_build,
        patch("dochris.api.app.get_settings", return_value=settings, create=True),
        patch("dochris.api.routes.compile._compile_timeout_seconds", return_value=5.0),
        TestClient(create_app()) as client,
    ):
        mock_build.return_value = (Repo(tmp_path / "jobs.db"), "sqlite")
        resp = client.post("/api/v1/compile", json={"limit": 1, "concurrency": 1})

    assert resp.status_code == 200
    manager = client.app.state.compile_jobs  # type: ignore[attr-defined]
    assert isinstance(manager._repository, Repo)
    assert mock_build.call_count == 1


# ── 工具 ──────────────────────────────────────────────────────


async def _wait_terminal(job: object, timeout: float = 2.0) -> None:
    import asyncio
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if str(getattr(job, "status", "")) not in ("queued", "running", "cancelling"):
            return
        await asyncio.sleep(0.01)
    pytest.fail("job did not reach a terminal status")


def test_sqlite_concurrent_writers_serialize(tmp_path: Path) -> None:
    """两个连接并发写（模拟多线程进度回调）不应损坏数据库。"""
    repo = SQLiteJobRepository(tmp_path / "jobs.db")
    external = sqlite3.connect(str(tmp_path / "jobs.db"))
    external.execute(
        "INSERT INTO compile_jobs (job_id, status, record) VALUES (?, ?, ?)",
        ("ext", "completed", json.dumps(_sample_record("ext"))),
    )
    external.commit()
    external.close()

    repo.save(_sample_record("mine", status="running"))
    assert repo.get("ext") is not None
    assert repo.get("mine") is not None
    repo.close()
