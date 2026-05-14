"""晋升路由 — POST /api/v1/promote/{src_id}"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Path

from dochris.api.schemas import ErrorResponse, PromoteRequest, PromoteResponse
from dochris.manifest import get_manifest
from dochris.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["promote"])


@router.post(
    "/promote/{src_id}",
    response_model=PromoteResponse,
    responses={
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def promote_artifact(
    src_id: str = Path(..., description="来源 ID，如 SRC-0001"),
    req: PromoteRequest | None = None,
    target: str | None = None,
) -> PromoteResponse:
    """将内容晋升到更高信任层级

    支持目标: wiki, curated
    """
    # 兼容 body 参数和 query 参数
    target_layer = (req.target if req else target) or "wiki"

    if target_layer not in ("wiki", "curated"):
        raise HTTPException(status_code=400, detail=f"不支持的目标层级: {target_layer}")

    settings = get_settings()
    workspace = settings.workspace

    manifest = get_manifest(workspace, src_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"未找到 manifest: {src_id}")

    try:
        if target_layer == "wiki":
            from dochris.promote import promote_to_wiki

            success = promote_to_wiki(workspace, src_id)
        else:
            from dochris.promote import promote_to_curated

            success = promote_to_curated(workspace, src_id)
    except Exception as exc:
        logger.exception("晋升失败")
        raise HTTPException(
            status_code=500, detail="晋升操作失败，请查看服务端日志获取详情"
        ) from exc

    if not success:
        return PromoteResponse(
            src_id=src_id,
            target=target_layer,
            success=False,
            message=f"晋升失败，请检查 {src_id} 的状态是否满足条件",
        )

    return PromoteResponse(
        src_id=src_id,
        target=target_layer,
        success=True,
        message=f"{src_id} 已晋升到 {target_layer}",
    )
