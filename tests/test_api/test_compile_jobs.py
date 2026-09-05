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


async def _wait_for_status(job: object, expected: str, timeout: float = 2.0) -> None:
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if getattr(job, "status", None) == expected:
            return
        await asyncio.sleep(0.01)
    pytest.fail(f"compile job did not reach {expected}")


@pytest.mark.asyncio
async def test_completed_job_survives_manager_recreation(tmp_path: Path) -> None:
    """已完成任务必须在 API 进程重启后仍可查询。"""
    store_path = tmp_path / "compile-jobs.json"
    manager = CompileJobManager(store_path=store_path)

    async def runner(*, progress_callback: Callable[..., None]) -> None:
        progress_callback(
            processed=2,
            compiled=2,
            failed=0,
            current_files=[],
        )

    job = manager.start(total=2, runner=runner)
    await _wait_for_status(job, "completed")

    restored = CompileJobManager(store_path=store_path).get(job.job_id)

    assert restored is not None
    assert restored.status == "completed"
    assert restored.processed == 2
    assert restored.compiled == 2
    assert restored.failed == 0


@pytest.mark.asyncio
async def test_partial_failures_mark_job_completed_with_errors(tmp_path: Path) -> None:
    """部分文档失败时任务不能伪装成完全成功。"""
    store_path = tmp_path / "compile-jobs.json"
    manager = CompileJobManager(store_path=store_path)

    async def runner(*, progress_callback: Callable[..., None]) -> None:
        progress_callback(
            processed=2,
            compiled=1,
            failed=1,
            current_files=[],
            failed_files=["SRC-0002"],
            failures=[{"src_id": "SRC-0002", "error": "RuntimeError: provider 502"}],
        )

    job = manager.start(total=2, runner=runner)
    await _wait_for_status(job, "completed_with_errors")

    restored = CompileJobManager(store_path=store_path).get(job.job_id)

    assert restored is not None
    assert restored.status == "completed_with_errors"
    assert restored.retryable is True
    assert restored.failed_files == ["SRC-0002"]
    assert restored.failure_details == [
        {"src_id": "SRC-0002", "error": "RuntimeError: provider 502"}
    ]
    assert "1 个文档失败" in restored.message

    response = restored.as_response()
    assert response.status == "completed_with_errors"
    assert response.failed_files == ["SRC-0002"]
    assert response.failure_details[0]["src_id"] == "SRC-0002"


@pytest.mark.asyncio
async def test_progress_without_failure_details_keeps_existing_values(tmp_path: Path) -> None:
    """旧回调签名（不含 failed_files）不能清空已有失败明细。"""
    manager = CompileJobManager()

    async def runner(*, progress_callback: Callable[..., None]) -> None:
        progress_callback(
            processed=1,
            compiled=0,
            failed=1,
            current_files=[],
            failed_files=["SRC-0001"],
            failures=[{"src_id": "SRC-0001", "error": "ValueError: bad input"}],
        )
        progress_callback(
            processed=2,
            compiled=1,
            failed=1,
            current_files=[],
        )

    job = manager.start(total=2, runner=runner)
    await _wait_for_status(job, "completed_with_errors")

    assert job.failed_files == ["SRC-0001"]
    assert job.failure_details[0]["error"] == "ValueError: bad input"


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


@pytest.mark.asyncio
async def test_job_timeout_budget_marks_job_failed() -> None:
    """JOB-06：超过任务级超时预算必须标记为 failed（含脱敏的超时说明）。"""
    manager = CompileJobManager()

    async def runner(*, progress_callback: Callable[..., None]) -> None:
        await asyncio.sleep(5)

    job = manager.start(total=1, runner=runner, timeout_seconds=0.05)
    await _wait_for_status(job, "failed")

    assert job.status == "failed"
    assert job.message == "编译任务超时"
    assert job.error is not None
    assert job.error.startswith("TimeoutError:")
    assert "0s" in job.error  # 0.05s 截断为 0s 预算描述
    assert manager.active() is None


@pytest.mark.asyncio
async def test_job_without_timeout_budget_runs_to_completion() -> None:
    """未配置超时预算时保持原有行为。"""

    async def runner(*, progress_callback: Callable[..., None]) -> None:
        progress_callback(processed=1, compiled=1, failed=0, current_files=[])

    manager = CompileJobManager()
    job = manager.start(total=1, runner=runner, timeout_seconds=None)
    await _wait_for_status(job, "completed")
    assert job.status == "completed"
