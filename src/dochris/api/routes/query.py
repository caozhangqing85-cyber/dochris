"""查询路由 — GET /api/v1/query"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from dochris.api.schemas import ErrorResponse, QueryResponse, SearchResult
from dochris.phases.phase3_query import query as do_query

logger = logging.getLogger(__name__)
router = APIRouter(tags=["query"])


def _to_search_result(item: dict[str, Any]) -> SearchResult:
    """将内部搜索结果转换为 API 响应格式"""
    return SearchResult(
        title=item.get("title", ""),
        content=item.get("content", item.get("text", item.get("definition", ""))),
        source=item.get("source", ""),
        file_path=item.get("file_path", ""),
        manifest_id=item.get("manifest_id", item.get("src_id")),
        score=item.get("score", 0.0),
    )


@router.get(
    "/query",
    response_model=QueryResponse,
    responses={500: {"model": ErrorResponse}},
)
async def query_knowledge_base(
    q: str = Query(..., min_length=1, description="查询关键词"),
    mode: str = Query(default="combined", description="查询模式"),
    top_k: int = Query(default=5, ge=1, le=50, description="返回结果数量"),
) -> QueryResponse:
    """查询知识库

    支持概念搜索、摘要搜索、向量检索和综合查询。
    """
    try:
        result = do_query(q, mode=mode, top_k=top_k, logger=logger)
    except Exception as exc:
        logger.exception("查询失败")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return QueryResponse(
        query=result["query"],
        mode=result["mode"],
        concepts=[_to_search_result(r) for r in result.get("concepts", [])],
        summaries=[_to_search_result(r) for r in result.get("summaries", [])],
        vector_results=[_to_search_result(r) for r in result.get("vector_results", [])],
        search_sources=result.get("search_sources", []),
        answer=result.get("answer"),
        time_seconds=result.get("time_seconds", 0.0),
    )
