"""Compile job lifecycle management.

任务运行态（进程内 dict）+ 持久化仓库（JobRepository）。
默认仓库由 API 装配层选择（SQLite WAL，见 job_repository.build_repository）；
``store_path=`` 参数保留为旧 JSON 用法的兼容入口。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from dochris.api.job_repository import (
    ACTIVE_STATUSES,
    JobRepository,
    JsonJobRepository,
)
from dochris.api.schemas import CompileResponse
from dochris.core.error_sanitizer import error_summary as _error_summary

logger = logging.getLogger(__name__)

__all__ = [
    "ACTIVE_STATUSES",
    "CompileJob",
    "CompileJobManager",
    "DEFAULT_LEASE_TTL_SECONDS",
    "DEFAULT_MAX_HISTORY",
    "RETRYABLE_STATUSES",
]

ProgressCallback = Callable[..., None]
CompileRunner = Callable[..., Awaitable[None]]
RETRYABLE_STATUSES = frozenset({"failed", "cancelled", "interrupted", "completed_with_errors"})
DEFAULT_MAX_HISTORY = 200


class JobPersistenceError(RuntimeError):
    """任务持久化失败（fail-closed：此时编译绝不启动）。"""


DEFAULT_LEASE_TTL_SECONDS = 300.0


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class CompileJob:
    """Mutable state for one compile request."""

    total: int
    job_id: str = field(default_factory=lambda: uuid4().hex)
    status: str = "queued"
    message: str = "编译任务已排队"
    processed: int = 0
    compiled: int = 0
    failed: int = 0
    current_files: list[str] = field(default_factory=list)
    failed_files: list[str] = field(default_factory=list)
    failure_details: list[dict[str, Any]] = field(default_factory=list)
    cancel_requested: bool = False
    concurrency: int = 1
    limit: int | None = None
    attempt: int = 1
    retry_of: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=_utc_now)
    started_at: str | None = None
    finished_at: str | None = None
    # JOB-05：幂等键与租约（由仓库持久化，跨重启恢复使用）
    idempotency_key: str | None = None
    lease_owner: str | None = None
    lease_expires_at: str | None = None
    heartbeat_at: str | None = None
    # 进程内控制位：心跳循环退出标记（不持久化）
    heartbeat_stop: bool = False

    @property
    def retryable(self) -> bool:
        return self.status in RETRYABLE_STATUSES

    def to_record(self) -> dict[str, Any]:
        """Return a JSON-serializable durable representation."""
        data = asdict(self)
        data.pop("heartbeat_stop", None)
        return data

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> CompileJob:
        """Restore known fields while tolerating future schema additions."""
        known_fields = {item.name for item in fields(cls)}
        return cls(**{key: value for key, value in record.items() if key in known_fields})

    def as_response(self) -> CompileResponse:
        return CompileResponse(
            job_id=self.job_id,
            status=self.status,
            message=self.message,
            total=self.total,
            processed=self.processed,
            compiled=self.compiled,
            failed=self.failed,
            current_files=list(self.current_files),
            failed_files=list(self.failed_files),
            failure_details=[dict(item) for item in self.failure_details],
            cancel_requested=self.cancel_requested,
            concurrency=self.concurrency,
            limit=self.limit,
            attempt=self.attempt,
            retry_of=self.retry_of,
            retryable=self.retryable,
            error=self.error,
            created_at=self.created_at,
            started_at=self.started_at,
            finished_at=self.finished_at,
        )


class CompileJobManager:
    """Own background tasks and expose their observable state."""

    def __init__(
        self,
        *,
        store_path: Path | None = None,
        repository: JobRepository | None = None,
        max_history: int = DEFAULT_MAX_HISTORY,
        owner_id: str | None = None,
        lease_ttl_seconds: float = DEFAULT_LEASE_TTL_SECONDS,
    ) -> None:
        if repository is not None:
            self._repository: JobRepository | None = repository
        elif store_path is not None:
            self._repository = JsonJobRepository(store_path)
        else:
            self._repository = None
        self._max_history = max(1, max_history)
        self._owner_id = owner_id or uuid4().hex
        self._lease_ttl = max(1.0, lease_ttl_seconds)
        # 多 worker 一致性：lease 仓库以 DB 为统一读模型（P1 review 修复）
        self._lease_aware = getattr(self._repository, "supports_lease", False)
        self._jobs: dict[str, CompileJob] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._heartbeats: dict[str, asyncio.Task[None]] = {}
        self._load()

    # -- 提交与运行 ------------------------------------------------

    def find_by_idempotency_key(self, key: str) -> CompileJob | None:
        """按幂等键查找任务（供路由在 no_work/dry_run 判定前解析重放）。"""
        if not key:
            return None
        return self._find_by_idempotency_key(key)

    def submit(
        self,
        total: int,
        runner: CompileRunner,
        *,
        concurrency: int = 1,
        limit: int | None = None,
        attempt: int = 1,
        retry_of: str | None = None,
        timeout_seconds: float | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[CompileJob, bool]:
        """提交编译任务。

        Returns:
            (job, created)：
            - created=True：新任务已创建并持久化（调用方可改写为 accepted）；
            - created=False：幂等重放或活动互斥返回了既有任务——调用方必须
              原样返回该任务，不得改写状态。
        Raises:
            JobPersistenceError: 持久化失败（fail-closed，编译绝不启动）。
        """
        # 幂等解析优先于活动互斥（与 SQLite claim 语义一致）
        if idempotency_key:
            replay = self._find_by_idempotency_key(idempotency_key)
            if replay is not None:
                return replay, False

        jobs_before = set(self._jobs)
        pre_active = self.active()

        job = self.start(
            total,
            runner,
            concurrency=concurrency,
            limit=limit,
            attempt=attempt,
            retry_of=retry_of,
            timeout_seconds=timeout_seconds,
            idempotency_key=idempotency_key,
        )
        created = job.job_id not in jobs_before and not (
            pre_active is not None and job.job_id == pre_active.job_id
        )
        return job, created

    def start(
        self,
        total: int,
        runner: CompileRunner,
        *,
        concurrency: int = 1,
        limit: int | None = None,
        attempt: int = 1,
        retry_of: str | None = None,
        timeout_seconds: float | None = None,
        idempotency_key: str | None = None,
    ) -> CompileJob:
        # 支持 BEGIN IMMEDIATE 事务的仓库（SQLite）：原子准入跨进程互斥 + 幂等，
        # 且插入即持久化（fail-closed：持久化失败时抛错，绝不启动无状态任务）
        claim = getattr(self._repository, "claim_job", None)
        if claim is not None:
            job = CompileJob(
                total=total,
                concurrency=concurrency,
                limit=limit,
                attempt=attempt,
                retry_of=retry_of,
                idempotency_key=idempotency_key,
            )
            try:
                claimed, existing_record = claim(job.to_record(), idempotency_key, ACTIVE_STATUSES)
            except Exception as exc:
                raise JobPersistenceError(f"任务持久化失败，编译未启动: {exc}") from exc
            if not claimed:
                # 稳定回填 _jobs：保证 POST 返回的任务随后 GET/取消可达
                existing_job = CompileJob.from_record(existing_record or job.to_record())
                self._jobs[existing_job.job_id] = existing_job
                return existing_job
            self._jobs[job.job_id] = job
            self._tasks[job.job_id] = asyncio.create_task(
                self._run(job, runner, timeout_seconds=timeout_seconds),
                name=f"dochris-compile-{job.job_id}",
            )
            return job

        # 旧仓库（JSON / 无持久化）：保留进程内互斥语义。
        # 幂等解析优先于活动互斥（与 SQLite claim 语义一致）
        if idempotency_key:
            existing = self._find_by_idempotency_key(idempotency_key)
            if existing is not None:
                return existing

        active = self.active()
        if active is not None:
            return active

        job = CompileJob(
            total=total,
            concurrency=concurrency,
            limit=limit,
            attempt=attempt,
            retry_of=retry_of,
            idempotency_key=idempotency_key,
        )
        self._jobs[job.job_id] = job
        if not self._persist(job):
            self._jobs.pop(job.job_id, None)
            raise JobPersistenceError(
                f"任务持久化失败，编译未启动（仓库: {type(self._repository).__name__ if self._repository else 'None'}）"
            )
        self._tasks[job.job_id] = asyncio.create_task(
            self._run(job, runner, timeout_seconds=timeout_seconds),
            name=f"dochris-compile-{job.job_id}",
        )
        return job

    def _find_by_idempotency_key(self, key: str) -> CompileJob | None:
        for job in reversed(self._jobs.values()):
            if job.idempotency_key == key:
                return job
        finder = getattr(self._repository, "find_by_idempotency_key", None)
        if finder is not None:
            record = finder(key)
            if record is not None:
                return CompileJob.from_record(record)
        return None

    def _observe_remote_cancel(self, job: CompileJob) -> bool:
        """检查仓库取消标记；命中则本地取消。返回是否命中。"""
        if job.cancel_requested:
            return True
        if not self._lease_aware or self._repository is None:
            return False
        try:
            if not self._repository.is_cancel_requested(job.job_id):
                return False
        except Exception:
            logger.warning("查询取消标记失败: %s", job.job_id, exc_info=True)
            return False
        job.cancel_requested = True
        job.status = "cancelling"
        job.message = "正在取消编译"
        task = self._tasks.get(job.job_id)
        if task is not None and not task.done():
            task.cancel()
        return True

    def _acquire_lease(self, job: CompileJob) -> None:
        from datetime import timedelta

        job.lease_owner = self._owner_id
        job.lease_expires_at = (datetime.now(UTC) + timedelta(seconds=self._lease_ttl)).isoformat()
        job.heartbeat_at = _utc_now()

    def _renew_lease(self, job: CompileJob) -> None:
        from datetime import timedelta

        job.lease_expires_at = (datetime.now(UTC) + timedelta(seconds=self._lease_ttl)).isoformat()
        job.heartbeat_at = _utc_now()

    def _release_lease(self, job: CompileJob) -> None:
        job.lease_owner = None
        job.lease_expires_at = None

    async def _heartbeat_loop(self, job: CompileJob) -> None:
        """JOB-05：运行期间周期性续租，进程死亡后 lease 自然过期。"""
        interval = self._lease_ttl / 3
        while job.status in ACTIVE_STATUSES and not job.heartbeat_stop:
            await asyncio.sleep(interval)
            if job.status not in ACTIVE_STATUSES or job.heartbeat_stop:
                break
            # 跨 worker 取消：先读专用取消标记（不会被 owner 续租/进度写覆盖），
            # 再续租落盘
            cancelling_requested = self._observe_remote_cancel(job)
            if cancelling_requested:
                job.cancel_requested = True
                job.status = "cancelling"
                job.message = "正在取消编译"
                task = self._tasks.get(job.job_id)
                if task is not None and not task.done():
                    task.cancel()
                break
            self._renew_lease(job)
            self._persist(job)

    async def _run(
        self,
        job: CompileJob,
        runner: CompileRunner,
        *,
        timeout_seconds: float | None = None,
    ) -> None:
        job.status = "running"
        job.message = "编译进行中"
        job.started_at = _utc_now()
        self._acquire_lease(job)
        self._persist(job)

        heartbeat = asyncio.create_task(
            self._heartbeat_loop(job), name=f"dochris-compile-hb-{job.job_id}"
        )
        self._heartbeats[job.job_id] = heartbeat

        async def _invoke() -> None:
            await runner(
                progress_callback=lambda **progress: self._update_progress(job, **progress)
            )

        try:
            if timeout_seconds is not None:
                # JOB-06：任务级超时预算，防止后台编译无限占用
                await asyncio.wait_for(_invoke(), timeout=timeout_seconds)
            else:
                await _invoke()
        except asyncio.CancelledError:
            job.status = "cancelled"
            job.message = "编译已取消"
            job.current_files = []
            job.finished_at = _utc_now()
        except TimeoutError:
            job.status = "failed"
            job.message = "编译任务超时"
            job.current_files = []
            job.error = f"TimeoutError: 任务超过 {timeout_seconds:.0f}s 超时预算被终止"
            job.finished_at = _utc_now()
            logger.error(
                "后台编译超时: %s",
                job.error,
                extra={"job_id": job.job_id},
            )
        except Exception as exc:
            job.status = "failed"
            job.message = "编译任务失败"
            job.current_files = []
            job.error = _error_summary(exc)
            job.finished_at = _utc_now()
            logger.error(
                "后台编译失败: %s",
                job.error,
                extra={"job_id": job.job_id},
            )
        else:
            job.current_files = []
            job.failed_files = sorted(job.failed_files)
            job.finished_at = _utc_now()
            if job.failed > 0:
                job.status = "completed_with_errors"
                job.message = f"编译完成，{job.failed} 个文档失败"
            else:
                job.status = "completed"
                job.message = "编译完成"
        finally:
            job.heartbeat_stop = True
            heartbeat.cancel()
            try:
                await heartbeat
            except (asyncio.CancelledError, Exception):
                pass
            self._heartbeats.pop(job.job_id, None)
            self._tasks.pop(job.job_id, None)
            self._release_lease(job)
            self._persist(job)

    def _update_progress(
        self,
        job: CompileJob,
        *,
        processed: int,
        compiled: int,
        failed: int,
        current_files: list[str],
        failed_files: list[str] | None = None,
        failures: list[dict[str, Any]] | None = None,
        **_extra: Any,
    ) -> None:
        job.processed = processed
        job.compiled = compiled
        job.failed = failed
        job.current_files = list(current_files)
        if failed_files is not None:
            job.failed_files = list(failed_files)
        if failures is not None:
            job.failure_details = [dict(item) for item in failures]
        # 跨 worker 取消：进度持久化前轮询取消标记（防止 owner 进度写覆盖取消标记）
        self._observe_remote_cancel(job)
        self._persist(job)

    # -- 查询 ------------------------------------------------------

    def _refresh_job(self, job_id: str) -> CompileJob | None:
        """从仓库刷新任务状态（仅 lease-aware 仓库；DB 为统一读模型）。"""
        if self._repository is None or not self._lease_aware:
            return self._jobs.get(job_id)
        try:
            record = self._repository.get(job_id)
        except Exception:
            logger.warning("刷新任务 %s 失败", job_id, exc_info=True)
            return self._jobs.get(job_id)
        if record is None:
            self._jobs.pop(job_id, None)
            return None
        job = CompileJob.from_record(record)
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> CompileJob | None:
        job = self._jobs.get(job_id)
        # 本进程未持有运行协程的任务，状态以仓库为准（其他 worker 可能已推进/完成）
        if job is not None and job_id in self._tasks:
            return job
        return self._refresh_job(job_id)

    def cancel(self, job_id: str) -> CompileJob | None:
        job = self.get(job_id)
        if job is None:
            return None

        task = self._tasks.get(job_id)
        if task is not None and not task.done():
            job.cancel_requested = True
            job.status = "cancelling"
            job.message = "正在取消编译"
            self._persist(job)
            task.cancel()
        elif self._lease_aware and self._repository is not None:
            # 跨 worker 取消：条件化写入（事务内重查状态，防止过期快照复活
            # 已终结任务），随后以仓库最新状态为准
            try:
                marker = getattr(self._repository, "mark_cancel", None)
                fresh = marker(job_id) if marker is not None else None
            except Exception:
                logger.warning("跨 worker 取消写入失败: %s", job_id, exc_info=True)
                fresh = None
            if fresh is not None:
                self._jobs[job_id] = CompileJob.from_record(fresh)
            else:
                job.cancel_requested = True
                job.status = "cancelling"
                job.message = "正在取消编译"
        return self._jobs.get(job_id, job)

    def active(self) -> CompileJob | None:
        if self._lease_aware and self._repository is not None:
            try:
                records = self._repository.find_active(ACTIVE_STATUSES)
            except Exception:
                logger.warning("查询活动任务失败", exc_info=True)
                records = []
            for record in records:
                job = CompileJob.from_record(record)
                self._jobs[job.job_id] = job
                return job
            return None
        return next(
            (job for job in reversed(self._jobs.values()) if job.status in ACTIVE_STATUSES),
            None,
        )

    def current(self) -> CompileJob | None:
        # 多 worker：首屏恢复可能落在任意 worker，最新任务以仓库为准
        history = self.history(limit=1)
        return history[0] if history else None

    def history(self, *, limit: int = 20) -> list[CompileJob]:
        """Return the newest jobs first, capped for API consumption."""
        if self._lease_aware and self._repository is not None:
            try:
                records = self._repository.list_all()
            except Exception:
                logger.warning("查询任务历史失败", exc_info=True)
                records = []
            jobs = [CompileJob.from_record(r) for r in reversed(records)]
            for job in jobs:
                self._jobs.setdefault(job.job_id, job)
            return jobs[:limit]
        return list(reversed(self._jobs.values()))[:limit]

    # -- 持久化 ----------------------------------------------------

    def _load(self) -> None:
        if self._repository is None:
            return
        try:
            records = self._repository.recover_stale_leases(self._owner_id)
        except Exception:
            logger.warning("无法加载编译任务历史", exc_info=True)
            return
        recovered_interrupted = False
        lease_aware = getattr(self._repository, "supports_lease", False)
        for record in records:
            if not isinstance(record, dict):
                continue
            job = CompileJob.from_record(record)
            if job.status in ACTIVE_STATUSES and not lease_aware:
                # 无 lease 语义的仓库（JSON）：活动任务按旧语义标记中断。
                # lease 仓库（SQLite）已在 recover_stale_leases 中处理：
                # 过期 lease → interrupted；他人有效 lease → 保留 running。
                job.status = "interrupted"
                job.message = "服务重启，编译任务已中断"
                job.current_files = []
                job.error = "ServiceRestart: 编译服务在任务完成前退出"
                job.finished_at = _utc_now()
                recovered_interrupted = True
            self._jobs[job.job_id] = job
        pruned = self._prune_history()
        if recovered_interrupted and self._repository is not None:
            # 恢复结果落盘，避免磁盘记录停留在外假的 running 状态
            for job in self._jobs.values():
                if job.status == "interrupted":
                    try:
                        self._repository.save(job.to_record())
                    except Exception:
                        logger.warning("无法持久化中断恢复结果", exc_info=True)
        _ = pruned

    def _persist(self, job: CompileJob) -> bool:
        """持久化单任务；返回是否成功（start 路径 fail-closed 依赖该返回值）。"""
        self._prune_history()
        if self._repository is None:
            return True
        try:
            self._repository.save(job.to_record())
        except Exception:
            logger.warning("无法保存编译任务 %s", job.job_id, exc_info=True)
            return False
        return True

    def _prune_history(self) -> bool:
        """Keep bounded terminal history while never discarding an active job."""
        excess = len(self._jobs) - self._max_history
        if excess <= 0:
            return False

        removable = [
            job_id for job_id, job in self._jobs.items() if job.status not in ACTIVE_STATUSES
        ]
        removed = False
        for job_id in removable[:excess]:
            self._jobs.pop(job_id, None)
            if self._repository is not None:
                try:
                    self._repository.delete(job_id)
                except Exception:
                    logger.warning("无法删除任务历史 %s", job_id, exc_info=True)
            removed = True
        return removed

    async def close(self) -> None:
        tasks = list(self._tasks.items())
        for job_id, task in tasks:
            if not task.done():
                self.cancel(job_id)
        if tasks:
            await asyncio.gather(*(task for _, task in tasks), return_exceptions=True)
        for heartbeat in self._heartbeats.values():
            heartbeat.cancel()
        if self._heartbeats:
            await asyncio.gather(*self._heartbeats.values(), return_exceptions=True)
            self._heartbeats.clear()
        if self._repository is not None:
            self._repository.close()
