"""编译路由 — POST /api/v1/compile"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from dochris.api.schemas import CompileRequest, CompileResponse, ErrorResponse
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
async def compile_documents(req: CompileRequest) -> CompileResponse:
    """触发文档编译

    后台异步执行编译任务，立即返回任务状态。
    """
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
        await do_compile_all(
            max_concurrent=req.concurrency,
            limit=req.limit,
            dry_run=False,
        )
    except Exception as exc:
        logger.exception("编译失败")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return CompileResponse(
        status="completed",
        message=f"编译完成: {total_to_compile} 个文档",
        total=total_to_compile,
    )
