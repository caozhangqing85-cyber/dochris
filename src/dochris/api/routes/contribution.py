"""候选知识管理路由 — Query-as-Contribution API"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from dochris.quality.query_contribution import (
    discard_candidate,
    list_candidates,
    promote_candidate,
)
from dochris.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["contribution"])


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
