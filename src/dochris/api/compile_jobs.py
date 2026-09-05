"""Process-local lifecycle tracking for background compile jobs."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from dochris.api.schemas import CompileResponse

logger = logging.getLogger(__name__)

ProgressCallback = Callable[..., None]
CompileRunner = Callable[..., Awaitable[None]]
ACTIVE_STATUSES = frozenset({"queued", "running", "cancelling"})
RETRYABLE_STATUSES = frozenset({"failed", "cancelled", "interrupted", "completed_with_errors"})
PARTIAL_STATUSES = frozenset({"completed_with_errors"})
DEFAULT_MAX_HISTORY = 200


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

    @property
    def retryable(self) -> bool:
        return self.status in RETRYABLE_STATUSES

    def to_record(self) -> dict[str, Any]:
        """Return a JSON-serializable durable representation."""
        return asdict(self)

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
        max_history: int = DEFAULT_MAX_HISTORY,
    ) -> None:
        self._store_path = store_path
        self._max_history = max(1, max_history)
        self._jobs: dict[str, CompileJob] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._load()

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
    ) -> CompileJob:
        active = self.active()
        if active is not None:
            return active

        job = CompileJob(
            total=total,
            concurrency=concurrency,
            limit=limit,
            attempt=attempt,
            retry_of=retry_of,
        )
        self._jobs[job.job_id] = job
        self._persist()
        self._tasks[job.job_id] = asyncio.create_task(
            self._run(job, runner, timeout_seconds=timeout_seconds),
            name=f"dochris-compile-{job.job_id}",
        )
        return job

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
        self._persist()

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
            self._tasks.pop(job.job_id, None)
            self._persist()

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
        self._persist()

    def get(self, job_id: str) -> CompileJob | None:
        return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> CompileJob | None:
        job = self.get(job_id)
        if job is None:
            return None

        task = self._tasks.get(job_id)
        if task is not None and not task.done():
            job.cancel_requested = True
            job.status = "cancelling"
            job.message = "正在取消编译"
            self._persist()
            task.cancel()
        return job

    def active(self) -> CompileJob | None:
        return next(
            (job for job in reversed(self._jobs.values()) if job.status in ACTIVE_STATUSES),
            None,
        )

    def current(self) -> CompileJob | None:
        return next(reversed(self._jobs.values()), None)

    def history(self, *, limit: int = 20) -> list[CompileJob]:
        """Return the newest jobs first, capped for API consumption."""
        return list(reversed(self._jobs.values()))[:limit]

    def _load(self) -> None:
        if self._store_path is None or not self._store_path.is_file():
            return
        try:
            payload = json.loads(self._store_path.read_text(encoding="utf-8"))
            records = payload.get("jobs", []) if isinstance(payload, dict) else []
            recovered_interrupted = False
            for record in records:
                if isinstance(record, dict):
                    job = CompileJob.from_record(record)
                    if job.status in ACTIVE_STATUSES:
                        job.status = "interrupted"
                        job.message = "服务重启，编译任务已中断"
                        job.current_files = []
                        job.error = "ServiceRestart: 编译服务在任务完成前退出"
                        job.finished_at = _utc_now()
                        recovered_interrupted = True
                    self._jobs[job.job_id] = job
            pruned = self._prune_history()
            if recovered_interrupted or pruned:
                self._persist()
        except (OSError, TypeError, ValueError):
            logger.warning("无法加载编译任务历史", exc_info=True)
            self._quarantine_corrupt_store()

    def _quarantine_corrupt_store(self) -> None:
        """Preserve an unreadable store for diagnosis and recreate a valid empty store."""
        if self._store_path is None or not self._store_path.exists():
            return
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        quarantine_path = self._store_path.with_name(
            f"{self._store_path.stem}.corrupt-{timestamp}{self._store_path.suffix}"
        )
        try:
            self._store_path.replace(quarantine_path)
        except OSError:
            logger.warning("无法隔离损坏的编译任务历史", exc_info=True)
        self._persist()

    def _persist(self) -> None:
        if self._store_path is None:
            return
        self._prune_history()
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._store_path.parent,
                prefix=f".{self._store_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = handle.name
                json.dump(
                    {"version": 1, "jobs": [job.to_record() for job in self._jobs.values()]},
                    handle,
                    ensure_ascii=False,
                    indent=2,
                )
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self._store_path)
        except OSError:
            logger.warning("无法保存编译任务历史", exc_info=True)
        finally:
            if temp_path is not None and os.path.exists(temp_path):
                os.unlink(temp_path)

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
            removed = True
        return removed

    async def close(self) -> None:
        tasks = list(self._tasks.items())
        for job_id, task in tasks:
            if not task.done():
                self.cancel(job_id)
        if tasks:
            await asyncio.gather(*(task for _, task in tasks), return_exceptions=True)


def _error_summary(exc: Exception) -> str:
    from dochris.core.error_sanitizer import error_summary

    return error_summary(exc)
