"""候选知识管理路由 — Query-as-Contribution API"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from dochris.api.schemas import QueryContributionRequest, QueryContributionResponse
from dochris.quality.query_contribution import (
    auto_contribute_from_query,
    discard_candidate,
    list_candidates,
    promote_candidate,
)
from dochris.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["contribution"])


@router.post(
    "/query/contribution",
    response_model=QueryContributionResponse,
    status_code=201,
)
async def create_query_contribution(
    payload: QueryContributionRequest,
) -> QueryContributionResponse:
    """将客户端确认的一次完整查询结果显式写入候选区。"""
    settings = get_settings()
    query_result = payload.model_dump()
    try:
        contribution = await asyncio.to_thread(
            auto_contribute_from_query,
            workspace_path=settings.workspace,
            query_result=query_result,
        )
    except OSError as exc:
        logger.exception("查询贡献写入失败")
        raise HTTPException(status_code=503, detail="候选知识存储暂不可用") from exc

    if contribution is None:
        raise HTTPException(status_code=422, detail="回答内容不足，未写入候选知识区")

    return QueryContributionResponse(
        id=contribution["id"],
        quality_score=contribution["quality_score"],
        needs_review=contribution.get("needs_review", True),
        auto_promoted=contribution.get("auto_promoted", False),
        status=contribution.get("status", "candidate"),
    )


@router.get("/candidates")
async def get_candidates(
    status: str | None = Query(default=None, description="过滤状态: candidate/promoted/discarded"),
    needs_review_only: bool = Query(default=False, description="只显示需审核的"),
) -> dict[str, Any]:
    """列出候选知识"""
    settings = get_settings()
    candidates = list_candidates(
        workspace_path=settings.workspace,
        status=status,
        needs_review_only=needs_review_only,
    )
    return {"candidates": candidates, "total": len(candidates)}


@router.post("/candidates/{candidate_id}/promote")
async def promote_candidate_api(candidate_id: str) -> dict[str, Any]:
    """将候选知识晋升到 wiki 层"""
    settings = get_settings()
    result = promote_candidate(
        workspace_path=settings.workspace,
        candidate_id=candidate_id,
        target="wiki",
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["reason"])
    return result


@router.post("/candidates/{candidate_id}/discard")
async def discard_candidate_api(
    candidate_id: str,
    reason: str = Query(default="manual_discard"),
) -> dict[str, Any]:
    """丢弃候选知识"""
    settings = get_settings()
    result = discard_candidate(
        workspace_path=settings.workspace,
        candidate_id=candidate_id,
        reason=reason,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["reason"])
    return result
