"""编译路由 — POST /api/v1/compile"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Query, Request

from dochris.api.compile_jobs import CompileJobManager, JobPersistenceError
from dochris.api.job_repository import build_repository
from dochris.api.schemas import (
    CompileJobFailuresResponse,
    CompileRequest,
    CompileResponse,
    ErrorResponse,
)
from dochris.manifest import get_all_manifests
from dochris.phases.phase2_compilation import compile_all as do_compile_all
from dochris.settings import get_default_workspace

logger = logging.getLogger(__name__)
router = APIRouter(tags=["compile"])


@router.post(
    "/compile",
    response_model=CompileResponse,
    responses={500: {"model": ErrorResponse}},
)
async def compile_documents(req: CompileRequest, request: Request) -> CompileResponse:
    """触发文档编译

    后台异步执行编译任务，立即返回任务状态。
    """
    manager = _get_compile_job_manager(request)
    idempotency_key = request.headers.get("Idempotency-Key", "").strip() or None

    # 幂等重放最优先：在 pending/no_work/dry_run 等任何判定之前解析，
    # 重放旧任务的 key 必须原样返回该任务（含其原始状态），不得被 no_work 顶替
    if idempotency_key:
        replay = manager.find_by_idempotency_key(idempotency_key)
        if replay is not None:
            return replay.as_response()

    # 无键请求走活动互斥早退（带键请求由 submit 的 created 标志决定语义）
    if idempotency_key is None:
        active_job = manager.active()
        if active_job is not None:
            return active_job.as_response()

    workspace = get_default_workspace()
    pending = get_all_manifests(workspace, status="ingested")
    total_to_compile = len(pending)

    if req.limit:
        total_to_compile = min(total_to_compile, req.limit)

    if total_to_compile == 0:
        return CompileResponse(
            status="no_work",
            message="没有待编译的文档",
            total=0,
        )

    if req.dry_run:
        return CompileResponse(
            status="dry_run",
            message=f"模拟运行: 将编译 {total_to_compile} 个文档",
            total=total_to_compile,
        )

    try:
        job, created = manager.submit(
            total_to_compile,
            lambda **kwargs: _run_compile_task(
                req.concurrency,
                req.limit,
                **kwargs,
            ),
            concurrency=req.concurrency,
            limit=req.limit,
            timeout_seconds=_compile_timeout_seconds(),
            idempotency_key=idempotency_key,
        )
    except JobPersistenceError as exc:
        logger.error("编译任务持久化失败: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="任务持久化失败，编译未启动（磁盘/数据库异常），请检查服务端日志后重试",
        ) from exc
    await asyncio.sleep(0)

    if not created:
        # 幂等重放（或活动互斥命中既有任务）：原样返回，不得改写为 accepted
        return job.as_response()

    return job.as_response().model_copy(
        update={
            "status": "accepted",
            "message": f"已提交后台编译任务: {total_to_compile} 个文档",
        }
    )


@router.get(
    "/compile/jobs",
    response_model=list[CompileResponse],
)
async def list_compile_jobs(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[CompileResponse]:
    """Return durable compile history, newest first."""
    return [job.as_response() for job in _get_compile_job_manager(request).history(limit=limit)]


@router.get(
    "/compile/jobs/current",
    response_model=CompileResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_current_compile_job(request: Request) -> CompileResponse:
    """Return the most recent compile job so a refreshed page can recover it."""
    job = _get_compile_job_manager(request).current()
    if job is None:
        raise HTTPException(status_code=404, detail="暂无编译任务")
    return job.as_response()


@router.get(
    "/compile/jobs/{job_id}",
    response_model=CompileResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_compile_job(job_id: str, request: Request) -> CompileResponse:
    """Return exact server-side progress for one compile job."""
    job = _get_compile_job_manager(request).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="编译任务不存在")
    return job.as_response()


@router.get(
    "/compile/jobs/{job_id}/failures",
    response_model=CompileJobFailuresResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_compile_job_failures(job_id: str, request: Request) -> CompileJobFailuresResponse:
    """Return the sanitized per-document failure report for one compile job.

    错误文本已统一脱敏（无 API key / 本机路径），可直接下载归档。
    """
    job = _get_compile_job_manager(request).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="编译任务不存在")
    return CompileJobFailuresResponse(
        job_id=job.job_id,
        status=job.status,
        failed=job.failed,
        failed_files=list(job.failed_files),
        failure_details=[dict(item) for item in job.failure_details],
    )


@router.post(
    "/compile/jobs/{job_id}/retry",
    response_model=CompileResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def retry_compile_job(job_id: str, request: Request) -> CompileResponse:
    """Create a linked retry using the original job parameters."""
    manager = _get_compile_job_manager(request)
    source = manager.get(job_id)
    if source is None:
        raise HTTPException(status_code=404, detail="编译任务不存在")
    if not source.retryable:
        raise HTTPException(status_code=409, detail="当前任务状态不可重试")
    if manager.active() is not None:
        raise HTTPException(status_code=409, detail="已有编译任务正在运行")

    pending = get_all_manifests(get_default_workspace(), status="ingested")
    total_to_compile = len(pending)
    if source.limit:
        total_to_compile = min(total_to_compile, source.limit)
    if total_to_compile == 0:
        return CompileResponse(
            status="no_work",
            message="没有待重试的文档",
            total=0,
            concurrency=source.concurrency,
            limit=source.limit,
            attempt=source.attempt + 1,
            retry_of=source.job_id,
        )

    try:
        job = manager.start(
            total_to_compile,
            lambda **kwargs: _run_compile_task(
                source.concurrency,
                source.limit,
                **kwargs,
            ),
            concurrency=source.concurrency,
            limit=source.limit,
            attempt=source.attempt + 1,
            retry_of=source.job_id,
            timeout_seconds=_compile_timeout_seconds(),
        )
    except JobPersistenceError as exc:
        logger.error("重试任务持久化失败: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="任务持久化失败，重试未启动（磁盘/数据库异常），请检查服务端日志后重试",
        ) from exc
    await asyncio.sleep(0)
    return job.as_response().model_copy(
        update={
            "status": "accepted",
            "message": f"已提交重试任务: {total_to_compile} 个文档",
        }
    )


@router.post(
    "/compile/jobs/{job_id}/cancel",
    response_model=CompileResponse,
    responses={404: {"model": ErrorResponse}},
)
async def cancel_compile_job(job_id: str, request: Request) -> CompileResponse:
    """Cancel one running compile job and return its latest state."""
    job = _get_compile_job_manager(request).cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="编译任务不存在")
    return job.as_response()


def _compile_timeout_seconds() -> float | None:
    """读取任务级超时预算（JOB-06）。未配置则不限制。"""
    raw = os.environ.get("DOCHRIS_COMPILE_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return None
    try:
        timeout = float(raw)
        return timeout if timeout > 0 else None
    except ValueError:
        logger.warning("无效的 DOCHRIS_COMPILE_TIMEOUT_SECONDS=%r，忽略超时预算", raw)
        return None


def _get_compile_job_manager(request: Request) -> CompileJobManager:
    manager = getattr(request.app.state, "compile_jobs", None)
    if manager is None:
        workspace = get_default_workspace()
        # JOB-03/04：仓库抽象 + SQLite WAL 默认（DOCHRIS_JOB_STORE=json 可回退）
        repository, _kind = build_repository(workspace)
        manager = CompileJobManager(repository=repository)
        request.app.state.compile_jobs = manager
    return manager


async def _run_compile_task(
    concurrency: int,
    limit: int | None,
    *,
    progress_callback: Callable[..., None],
) -> None:
    """后台执行编译任务，避免长时间占用 HTTP 请求"""
    await do_compile_all(
        max_concurrent=concurrency,
        limit=limit,
        dry_run=False,
        progress_callback=progress_callback,
    )
