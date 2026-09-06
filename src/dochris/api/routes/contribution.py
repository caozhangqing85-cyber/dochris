"""候选知识管理路由 — Query-as-Contribution API"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from dochris.api.preview import preview_envelope
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


@router.get("/candidates/{candidate_id}")
async def get_candidate_detail(candidate_id: str) -> dict[str, Any]:
    """候选详情（UX-03）：全文、来源、矛盾检测与晋升最终 diff 计划。"""
    from dochris.quality.query_contribution import _safe_filename

    settings = get_settings()
    ws = Path(settings.workspace)
    meta_file = ws / "outputs" / "candidates" / "meta" / f"{candidate_id}.json"
    if not meta_file.exists():
        raise HTTPException(status_code=404, detail=f"候选不存在: {candidate_id}")
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"候选元数据读取失败: {exc}") from exc

    full_text = ""
    content_rel = str(meta.get("file", ""))
    content_file = ws / content_rel if content_rel else None
    content_exists = bool(content_file and content_file.exists())
    if content_exists and content_file is not None:
        try:
            full_text = content_file.read_text(encoding="utf-8")
        except OSError:
            full_text = ""

    # 晋升最终 diff 计划：与 promote_candidate 的写入逻辑保持一致
    # （摘要写入 wiki/summaries/{safe_title}.md，同 名已存在时改用 _hash 后缀）
    promote_plan: dict[str, Any] = {"changes": [], "blockers": []}
    if meta.get("status") == "candidate":
        if not content_exists or content_file is None:
            promote_plan["blockers"].append("候选内容文件缺失")
        else:
            wiki_dir = ws / "wiki" / "summaries"
            safe_title = _safe_filename(str(meta.get("title", "")))
            planned = wiki_dir / f"{safe_title}.md"
            if planned.exists():
                planned = wiki_dir / f"{safe_title}_{str(meta.get('content_hash', ''))[:4]}.md"
            promote_plan["changes"].append(
                {
                    "path": str(planned.relative_to(ws)),
                    "action": "identical"
                    if planned.exists() and planned.read_bytes() == content_file.read_bytes()
                    else "overwrite"
                    if planned.exists()
                    else "create",
                    "size_bytes": content_file.stat().st_size,
                }
            )
        for concept in meta.get("concepts_extracted", []):
            name = str(concept.get("name", "")) if isinstance(concept, dict) else str(concept)
            if not name:
                continue
            concept_file = ws / "wiki" / "concepts" / f"{_safe_filename(name)}.md"
            promote_plan["changes"].append(
                {
                    "path": str(concept_file.relative_to(ws)),
                    "action": "identical" if concept_file.exists() else "create",
                }
            )

    return {
        **meta,
        "full_text": full_text,
        "promote_plan": promote_plan,
    }


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
    preview: bool = Query(default=False, description="SEC-05：仅返回预览，不执行丢弃"),
) -> dict[str, Any]:
    """丢弃候选知识

    SEC-05：``preview=true`` 时不执行丢弃，返回将被丢弃的候选内容与元数据。
    """
    settings = get_settings()
    if preview:
        meta_file = (
            Path(settings.workspace) / "outputs" / "candidates" / "meta" / f"{candidate_id}.json"
        )
        if not meta_file.exists():
            raise HTTPException(status_code=404, detail=f"候选不存在: {candidate_id}")
        try:
            target = json.loads(meta_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=500, detail=f"候选元数据读取失败: {exc}") from exc
        return preview_envelope(
            "discard_candidate",
            f"将把候选 {candidate_id} 标记为 discarded（不删除任何文件）",
            [
                {
                    "id": target.get("id"),
                    "query": target.get("query", ""),
                    "status": target.get("status"),
                    "quality_score": target.get("quality_score"),
                    "to_status": "discarded",
                    "reason": reason,
                }
            ],
        )
    result = discard_candidate(
        workspace_path=settings.workspace,
        candidate_id=candidate_id,
        reason=reason,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["reason"])
    return result
