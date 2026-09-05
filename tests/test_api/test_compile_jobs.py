"""编译作业管理器生命周期测试。"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from pathlib import Path

import pytest

from dochris.api.compile_jobs import CompileJobManager

pytestmark = pytest.mark.fast


async def _wait_for_status(job: object, expected: str) -> None:
    for _ in range(20):
        if getattr(job, "status", None) == expected:
            return
        await asyncio.sleep(0)
    pytest.fail(f"compile job did not reach {expected}")


@pytest.mark.asyncio
async def test_completed_job_survives_manager_recreation(tmp_path: Path) -> None:
    """已完成任务必须在 API 进程重启后仍可查询。"""
    store_path = tmp_path / "compile-jobs.json"
    manager = CompileJobManager(store_path=store_path)

    async def runner(*, progress_callback: Callable[..., None]) -> None:
        progress_callback(
            processed=2,
            compiled=1,
            failed=1,
            current_files=[],
        )

    job = manager.start(total=2, runner=runner)
    await _wait_for_status(job, "completed")

    restored = CompileJobManager(store_path=store_path).get(job.job_id)

    assert restored is not None
    assert restored.status == "completed"
    assert restored.processed == 2
    assert restored.compiled == 1
    assert restored.failed == 1


@pytest.mark.asyncio
async def test_persisted_history_is_bounded_to_newest_terminal_jobs(tmp_path: Path) -> None:
    """长期运行不能让编译历史文件无限增长。"""
    store_path = tmp_path / "compile-jobs.json"
    manager = CompileJobManager(store_path=store_path, max_history=2)
    job_ids: list[str] = []

    async def runner(*, progress_callback: Callable[..., None]) -> None:
        progress_callback(
            processed=1,
            compiled=1,
            failed=0,
            current_files=[],
        )

    for _ in range(3):
        job = manager.start(total=1, runner=runner)
        job_ids.append(job.job_id)
        await _wait_for_status(job, "completed")

    restored = CompileJobManager(store_path=store_path, max_history=2)

    assert [job.job_id for job in restored.history(limit=10)] == list(reversed(job_ids[-2:]))
    assert restored.get(job_ids[0]) is None


def test_corrupt_history_is_quarantined_and_reinitialized(tmp_path: Path) -> None:
    """损坏的历史文件不能让接口永久失去持久化能力。"""
    store_path = tmp_path / "compile-jobs.json"
    store_path.write_text("{broken-json", encoding="utf-8")

    manager = CompileJobManager(store_path=store_path)

    assert manager.history(limit=10) == []
    assert json.loads(store_path.read_text(encoding="utf-8")) == {
        "version": 1,
        "jobs": [],
    }
    [quarantined] = list(tmp_path.glob("compile-jobs.corrupt-*.json"))
    assert quarantined.read_text(encoding="utf-8") == "{broken-json"


@pytest.mark.asyncio
async def test_failed_job_redacts_secrets_and_local_paths_before_persisting(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """浏览器历史和磁盘记录都不能包含 provider 密钥或本机绝对路径。"""
    store_path = tmp_path / "compile-jobs.json"
    manager = CompileJobManager(store_path=store_path)
    caplog.set_level(logging.ERROR, logger="dochris.api.compile_jobs")
    secret = "sk-live-super-secret-token"
    private_path = "/Users/alice/private/customer-notes.md"

    async def runner(*, progress_callback: Callable[..., None]) -> None:
        del progress_callback
        raise RuntimeError(
            f"Authorization: Bearer {secret}; OPENAI_API_KEY={secret}; failed at {private_path}"
        )

    job = manager.start(total=1, runner=runner)
    await _wait_for_status(job, "failed")

    restored = CompileJobManager(store_path=store_path).get(job.job_id)
    raw_store = store_path.read_text(encoding="utf-8")

    assert restored is not None
    assert restored.error is not None
    assert restored.error.startswith("RuntimeError:")
    assert "[REDACTED]" in restored.error
    assert "<path>" in restored.error
    for sensitive in (secret, "Bearer", "OPENAI_API_KEY", private_path, "/Users/"):
        assert sensitive not in restored.error
        assert sensitive not in raw_store
        assert sensitive not in caplog.text


@pytest.mark.asyncio
async def test_running_job_is_restored_as_interrupted(tmp_path: Path) -> None:
    """进程消失后的活动任务不能在新进程中伪装成仍在运行。"""
    store_path = tmp_path / "compile-jobs.json"
    manager = CompileJobManager(store_path=store_path)
    started = asyncio.Event()

    async def runner(*, progress_callback: Callable[..., None]) -> None:
        progress_callback(
            processed=1,
            compiled=1,
            failed=0,
            current_files=["SRC-0002"],
        )
        started.set()
        await asyncio.Event().wait()

    job = manager.start(total=2, runner=runner)
    await asyncio.wait_for(started.wait(), timeout=1.0)

    try:
        restored_manager = CompileJobManager(store_path=store_path)
        restored = restored_manager.get(job.job_id)

        assert restored is not None
        assert restored.status == "interrupted"
        assert restored.message == "服务重启，编译任务已中断"
        assert restored.processed == 1
        assert restored.current_files == []
        assert restored_manager.active() is None
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_close_cancels_and_waits_for_running_jobs() -> None:
    """服务关闭不能遗留仍在运行的编译协程。"""
    manager = CompileJobManager()
    started = asyncio.Event()
    runner_cancelled = asyncio.Event()

    async def runner(*, progress_callback: Callable[..., None]) -> None:
        progress_callback(
            processed=0,
            compiled=0,
            failed=0,
            current_files=["SRC-0001"],
        )
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            runner_cancelled.set()

    job = manager.start(total=1, runner=runner)
    await asyncio.wait_for(started.wait(), timeout=1.0)

    close = getattr(manager, "close", None)
    assert close is not None, "CompileJobManager 必须提供异步关闭方法"
    await close()

    assert runner_cancelled.is_set()
    assert job.status == "cancelled"
    assert job.cancel_requested is True
    assert job.current_files == []
    assert manager.active() is None
