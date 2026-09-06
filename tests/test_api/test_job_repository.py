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

from dochris.api.compile_jobs import CompileJobManager, JobPersistenceError
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


def test_sqlite_idempotency_key_is_unique(tmp_path: Path) -> None:
    """幂等键带部分唯一约束：不同任务不能共享同一键（原子准入的兜底）。"""
    import sqlite3

    repo = SQLiteJobRepository(tmp_path / "jobs.db")
    repo.save({**_sample_record("first"), "idempotency_key": "op-1"})
    with pytest.raises(sqlite3.IntegrityError):
        repo.save({**_sample_record("second"), "idempotency_key": "op-1"})

    found = repo.find_by_idempotency_key("op-1")
    assert found is not None
    assert found["job_id"] == "first"
    assert repo.find_by_idempotency_key("nope") is None
    repo.close()


def test_claim_job_rejects_when_active_job_exists(tmp_path: Path) -> None:
    repo = SQLiteJobRepository(tmp_path / "jobs.db")
    claimed, existing = repo.claim_job(
        _sample_record("worker-a", status="queued"), None, {"queued", "running", "cancelling"}
    )
    assert claimed is True and existing is None

    # 另一个 worker 的准入被活动任务拒绝（lease 未过期）
    claimed2, existing2 = repo.claim_job(
        _sample_record("worker-b", status="queued"), "op-2", {"queued", "running", "cancelling"}
    )
    assert claimed2 is False
    assert existing2 is not None and existing2["job_id"] == "worker-a"
    assert repo.get("worker-b") is None  # 拒绝时不得落库
    repo.close()


def test_claim_job_ignores_expired_lease_when_mutexting(tmp_path: Path) -> None:
    from datetime import UTC, datetime, timedelta

    repo = SQLiteJobRepository(tmp_path / "jobs.db")
    expired = (datetime.now(UTC) - timedelta(seconds=5)).isoformat()
    repo.save(
        {
            **_sample_record("stale", status="running"),
            "lease_owner": "dead-process",
            "lease_expires_at": expired,
        }
    )

    claimed, _ = repo.claim_job(
        _sample_record("fresh", status="queued"), None, {"queued", "running", "cancelling"}
    )
    assert claimed is True  # 过期 lease 不阻塞新任务（自愈）
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


@pytest.mark.asyncio
async def test_cross_process_mutex_second_manager_returns_existing_job(tmp_path: Path) -> None:
    """两个 manager（模拟两个 API worker）必须互斥：后者拿回前者的任务。"""
    db_path = tmp_path / "jobs.db"
    started = asyncio.Event()

    async def runner(*, progress_callback: Callable[..., None]) -> None:
        started.set()
        await asyncio.Event().wait()

    manager_a = CompileJobManager(repository=SQLiteJobRepository(db_path), owner_id="worker-a")
    job_a = manager_a.start(2, runner)
    await asyncio.wait_for(started.wait(), timeout=1.0)

    manager_b = CompileJobManager(repository=SQLiteJobRepository(db_path), owner_id="worker-b")
    job_b = manager_b.start(2, runner)
    assert job_b.job_id == job_a.job_id
    assert job_b.status == "running"

    await manager_a.close()
    await manager_b.close()


@pytest.mark.asyncio
async def test_start_is_fail_closed_when_persistence_fails(tmp_path: Path) -> None:
    """持久化失败时编译绝不启动（JobPersistenceError）。"""
    from dochris.api.compile_jobs import JobPersistenceError

    repo = SQLiteJobRepository(tmp_path / "jobs.db")
    manager = CompileJobManager(repository=repo)

    async def runner(*, progress_callback: Callable[..., None]) -> None:
        raise AssertionError("runner 不应被调用")

    with patch.object(repo, "claim_job", side_effect=sqlite3.OperationalError("disk I/O error")):
        with pytest.raises(JobPersistenceError):
            manager.start(1, runner)

    assert manager.active() is None
    assert repo.get.__module__  # repo 仍可用
    repo.close()


@pytest.mark.asyncio
async def test_legacy_json_start_is_fail_closed_on_save_failure(tmp_path: Path) -> None:
    store = tmp_path / "compile-jobs.json"
    manager = CompileJobManager(store_path=store)

    async def runner(*, progress_callback: Callable[..., None]) -> None:
        raise AssertionError("runner 不应被调用")

    with patch.object(manager._repository, "save", side_effect=OSError("No space left on device")):
        with pytest.raises(JobPersistenceError):
            manager.start(1, runner)

    assert manager.active() is None
    await manager.close()


@pytest.mark.asyncio
async def test_worker_b_sees_worker_a_completion(tmp_path: Path) -> None:
    """统一读模型：A 完成后 B 的 get/active/history 必须反映 completed。"""
    db_path = tmp_path / "jobs.db"
    release = asyncio.Event()

    async def runner(*, progress_callback: Callable[..., None]) -> None:
        await release.wait()

    started = asyncio.Event()

    async def runner_wait_start(*, progress_callback: Callable[..., None]) -> None:
        started.set()
        await release.wait()

    manager_a = CompileJobManager(repository=SQLiteJobRepository(db_path), owner_id="worker-a")
    manager_b = CompileJobManager(repository=SQLiteJobRepository(db_path), owner_id="worker-b")
    job = manager_a.start(2, runner_wait_start)

    try:
        await asyncio.wait_for(started.wait(), timeout=1.0)
        running_from_b = manager_b.get(job.job_id)
        assert running_from_b is not None and running_from_b.status == "running"
        assert manager_b.active() is not None

        release.set()
        await _wait_terminal(job, timeout=2.0)
        await asyncio.sleep(0.05)  # 等 A 侧最终状态落库

        completed_from_b = manager_b.get(job.job_id)
        assert completed_from_b is not None
        assert completed_from_b.status == "completed"
        assert manager_b.active() is None  # 不能永久返回 running
        history = manager_b.history(limit=5)
        assert history and history[0].status == "completed"
    finally:
        await manager_a.close()
        await manager_b.close()


@pytest.mark.asyncio
async def test_cross_worker_cancel_reaches_owner_via_heartbeat(tmp_path: Path) -> None:
    """B 取消任务 → cancelling 落库 → A 的心跳检测并本地取消。"""
    db_path = tmp_path / "jobs.db"
    started = asyncio.Event()

    async def runner(*, progress_callback: Callable[..., None]) -> None:
        started.set()
        await asyncio.Event().wait()

    manager_a = CompileJobManager(
        repository=SQLiteJobRepository(db_path), owner_id="worker-a", lease_ttl_seconds=0.3
    )
    manager_b = CompileJobManager(
        repository=SQLiteJobRepository(db_path), owner_id="worker-b", lease_ttl_seconds=0.3
    )
    job = manager_a.start(2, runner)
    await asyncio.wait_for(started.wait(), timeout=1.0)

    cancelled_from_b = manager_b.cancel(job.job_id)
    assert cancelled_from_b is not None and cancelled_from_b.status == "cancelling"

    for _ in range(60):
        if job.status == "cancelled":
            break
        await asyncio.sleep(0.05)
    assert job.status == "cancelled", f"A 侧未跟进取消: {job.status}"

    await manager_a.close()
    await manager_b.close()


def test_sqlite_index_upgrades_to_unique_on_old_databases(tmp_path: Path) -> None:
    """旧库已有同名普通索引时，新版本必须升级为唯一索引（P2 review）。"""
    import sqlite3

    db_path = tmp_path / "legacy.db"
    legacy = sqlite3.connect(str(db_path))
    legacy.executescript(
        """
        CREATE TABLE compile_jobs (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL UNIQUE,
            idempotency_key TEXT,
            status TEXT NOT NULL,
            lease_owner TEXT,
            lease_expires_at TEXT,
            heartbeat_at TEXT,
            record TEXT NOT NULL
        );
        CREATE INDEX idx_compile_jobs_idem ON compile_jobs(idempotency_key);
        """
    )
    legacy.commit()
    legacy.close()

    repo = SQLiteJobRepository(db_path)
    repo.save({**_sample_record("first"), "idempotency_key": "dup"})
    with pytest.raises(sqlite3.IntegrityError):
        repo.save({**_sample_record("second"), "idempotency_key": "dup"})

    unique = repo._conn.execute(
        "SELECT DISTINCT sql FROM sqlite_master WHERE name = 'idx_compile_jobs_idem'"
    ).fetchone()[0]
    assert "UNIQUE" in unique.upper()
    repo.close()


@pytest.mark.asyncio
async def test_retry_route_returns_503_when_persistence_fails(tmp_path: Path) -> None:
    """retry 路径与首次编译一样 fail-closed（P2 review）。"""

    from fastapi.testclient import TestClient

    from dochris.api.app import create_app

    settings = type("S", (), {"workspace": str(tmp_path)})()
    app = create_app()

    with (
        patch("dochris.api.routes.compile.get_default_workspace", return_value=str(tmp_path)),
        patch(
            "dochris.api.routes.compile.get_all_manifests",
            return_value=[{"id": "SRC-0001", "status": "ingested"}],
        ),
        patch("dochris.phases.phase2_compilation.get_all_manifests", return_value=[]),
        patch("dochris.api.app.get_settings", return_value=settings, create=True),
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        # 先造一个可重试（failed）任务：编译 runner 抛错使任务进入 failed
        with patch(
            "dochris.api.routes.compile.do_compile_all",
            side_effect=RuntimeError("boom"),
        ):
            ok = client.post(
                "/api/v1/compile",
                json={"concurrency": 1},
                headers={"Idempotency-Key": "seed-1"},
            )
            assert ok.status_code == 200
            job_id = ok.json()["job_id"]
            for _ in range(50):
                state = client.get(f"/api/v1/compile/jobs/{job_id}").json()
                if state["status"] == "failed":
                    break
                import time

                time.sleep(0.02)
            assert state["status"] == "failed"

        with patch(
            "dochris.api.compile_jobs.CompileJobManager.start",
            side_effect=__import__(
                "dochris.api.compile_jobs", fromlist=["JobPersistenceError"]
            ).JobPersistenceError("disk full"),
        ):
            resp = client.post(f"/api/v1/compile/jobs/{job_id}/retry")

        assert resp.status_code == 503
        assert "持久化失败" in resp.json()["detail"]


def test_sqlite_upgrade_dedupes_legacy_duplicate_keys(tmp_path: Path) -> None:
    """旧库存在重复幂等键时，升级必须确定性去重（保留最新）且服务可启动。"""
    import sqlite3

    db_path = tmp_path / "legacy-dup.db"
    legacy = sqlite3.connect(str(db_path))
    legacy.executescript(
        """
        CREATE TABLE compile_jobs (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL UNIQUE,
            idempotency_key TEXT,
            status TEXT NOT NULL,
            lease_owner TEXT,
            lease_expires_at TEXT,
            heartbeat_at TEXT,
            record TEXT NOT NULL
        );
        CREATE INDEX idx_compile_jobs_idem ON compile_jobs(idempotency_key);
        """
    )
    for job_id, key in (("old-1", "dup"), ("old-2", "dup"), ("old-3", "keep")):
        legacy.execute(
            "INSERT INTO compile_jobs (job_id, idempotency_key, status, record) VALUES (?, ?, ?, ?)",
            (job_id, key, "completed", json.dumps(_sample_record(job_id))),
        )
    legacy.commit()
    legacy.close()

    repo = SQLiteJobRepository(db_path)

    # 去重策略：保留全部历史；最新 old-2 持有键，old-1 键置空，old-3 不受影响
    assert repo.get("old-1") is not None, "去重不得删除任务历史"
    found = repo.find_by_idempotency_key("dup")
    assert found is not None and found["job_id"] == "old-2"
    assert repo.get("old-1")["idempotency_key"] is None
    with pytest.raises(sqlite3.IntegrityError):
        repo.save({**_sample_record("another"), "idempotency_key": "dup"})
    repo.close()


@pytest.mark.asyncio
async def test_replaying_completed_key_wins_over_unrelated_active(tmp_path: Path) -> None:
    """API 回归：旧任务已完成 + 存在无关活动任务 + 重放旧 key → 必须返回原任务。"""
    db_path = tmp_path / "jobs.db"
    started_b = asyncio.Event()

    async def runner_a(*, progress_callback: Callable[..., None]) -> None:
        progress_callback(processed=1, compiled=1, failed=0, current_files=[])

    async def runner_b(*, progress_callback: Callable[..., None]) -> None:
        started_b.set()
        await asyncio.Event().wait()

    manager_a = CompileJobManager(repository=SQLiteJobRepository(db_path), owner_id="worker-a")
    manager_b = CompileJobManager(repository=SQLiteJobRepository(db_path), owner_id="worker-b")

    original = manager_a.start(1, runner_a, idempotency_key="key-original")
    await _wait_terminal(original)

    # 无关任务 B 开始运行（无幂等键）
    job_b = manager_b.start(2, runner_b)
    await asyncio.wait_for(started_b.wait(), timeout=1.0)
    assert job_b.job_id != original.job_id

    # 重放旧 key：必须返回原任务 A，而不是任务 B
    replayed = manager_a.start(1, runner_b, idempotency_key="key-original")
    assert replayed.job_id == original.job_id
    assert replayed.status == "completed"

    await manager_a.close()
    await manager_b.close()


def test_save_quarantines_corrupt_history_before_overwrite(tmp_path: Path) -> None:
    """损坏 JSON 必须先隔离（保留证据），再写新快照——禁止静默覆盖。"""
    store = tmp_path / "compile-jobs.json"
    store.write_text("{corrupted-evidence", encoding="utf-8")

    repo = JsonJobRepository(store)
    repo.save(_sample_record("fresh"))

    quarantined = list(tmp_path.glob("compile-jobs.corrupt-*.json"))
    assert len(quarantined) == 1, "损坏文件必须被隔离而不是覆盖"
    assert quarantined[0].read_text(encoding="utf-8") == "{corrupted-evidence"
    assert repo.get("fresh") is not None
