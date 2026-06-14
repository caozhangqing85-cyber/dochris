"""查询路由 — GET /api/v1/query, GET /api/v1/query/stream"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from dochris.api.schemas import ErrorResponse, QueryResponse, SearchResult
from dochris.observability.tracing import get_current_trace_id
from dochris.phases import query_engine
from dochris.phases.phase3_query import query_async as do_query_async
from dochris.rag.schemas import normalize_score
from dochris.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["query"])


def _to_search_result(
    item: dict[str, Any],
    score_type: str = "keyword",
) -> SearchResult:
    """将内部搜索结果转换为 API 响应格式

    Args:
        item: 内部搜索结果字典
        score_type: "keyword" 或 "vector"，决定归一化策略
    """
    raw_score = item.get("score", 0.0)
    if score_type == "vector":
        normalized = normalize_score(raw_score, "cosine_distance", raw_distance=raw_score)
    else:
        normalized = normalize_score(raw_score, "keyword")

    return SearchResult(
        title=item.get("title", ""),
        content=item.get("content", item.get("text", item.get("definition", ""))),
        source=item.get("source", ""),
        file_path=item.get("file_path", ""),
        manifest_id=item.get("manifest_id", item.get("src_id")),
        score=normalized,
        rerank_score=item.get("rerank_score"),
        rank_source="rerank" if item.get("rerank_score") is not None else score_type,
    )


@router.get(
    "/query",
    response_model=QueryResponse,
    responses={500: {"model": ErrorResponse}},
)
async def query_knowledge_base(
    q: str = Query(..., min_length=1, max_length=500, description="查询关键词"),
    mode: str = Query(default="combined", description="查询模式"),
    top_k: int = Query(default=5, ge=1, le=50, description="返回结果数量"),
    contribute: bool = Query(
        default=False, description="启用 Query-as-Contribution，将回答写回知识库"
    ),
    rerank: bool = Query(default=False, description="启用 Reranker 重排序"),
) -> QueryResponse:
    """查询知识库

    支持概念搜索、摘要搜索、向量检索和综合查询。
    当 contribute=true 时，高质量回答会自动写入候选区（outputs/candidates/）。
    """
    settings = get_settings()
    workspace_path = settings.workspace

    try:
        result = await do_query_async(
            q,
            mode=mode,
            top_k=top_k,
            logger=logger,
            contribute=contribute,
            workspace_path=workspace_path,
            rerank=rerank,
        )
    except Exception as exc:
        logger.exception("查询失败")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    response = QueryResponse(
        query=result["query"],
        mode=result["mode"],
        concepts=[_to_search_result(r, "keyword") for r in result.get("concepts", [])],
        summaries=[_to_search_result(r, "keyword") for r in result.get("summaries", [])],
        vector_results=[_to_search_result(r, "vector") for r in result.get("vector_results", [])],
        search_sources=result.get("search_sources", []),
        answer=result.get("answer"),
        time_seconds=result.get("time_seconds", 0.0),
        reranked="reranker" in result.get("search_sources", []),
        trace_id=get_current_trace_id(),
    )

    return response


@router.get(
    "/query/stream",
    responses={500: {"model": ErrorResponse}},
)
async def query_stream(
    q: str = Query(..., min_length=1, max_length=500, description="查询关键词"),
    mode: str = Query(default="combined", description="查询模式"),
    top_k: int = Query(default=5, ge=1, le=50, description="返回结果数量"),
    rerank: bool = Query(default=False, description="启用 Reranker 重排序"),
) -> StreamingResponse:
    """流式查询知识库 — SSE 端点

    先返回检索结果（concepts, summaries, vector_results），
    然后流式返回 LLM 生成的回答。

    SSE 事件格式 (v=1):
    - event: meta         — 查询元信息 (query, mode, search_sources)
    - event: retrieval    — 检索结果 JSON (concepts + summaries + vector_results)
    - event: answer_delta — LLM 回答的一个文本 chunk
    - event: done         — 流结束（含 trace_id）
    - event: error        — 错误信息
    - event: ping         — 心跳保活
    """

    async def _async_generate() -> Any:
        try:
            import asyncio
            import time

            from dochris.api.sse import (
                sse_answer_delta,
                sse_done_event,
                sse_error_event,
                sse_meta_event,
                sse_retrieval_event,
            )
            from dochris.phases.phase3_query import (
                search_concepts,
                search_summaries,
                vector_search,
            )

            start = time.time()

            concepts: list[dict] = []
            summaries: list[dict] = []
            vector_results: list[dict] = []
            search_sources: list[str] = []

            # 1a. 快速检索：概念 + 摘要（本地文件，毫秒级）
            if mode in ("concept", "combined"):
                concepts = search_concepts(q, top_k)
                if concepts:
                    search_sources.append(concepts[0].get("source", ""))

            if mode in ("summary", "combined"):
                summaries = search_summaries(q, top_k)
                if summaries:
                    search_sources.append(summaries[0].get("source", ""))

            # 2. 立即发送 meta 事件（不等向量搜索）
            yield sse_meta_event(
                query=q,
                mode=mode,
                search_sources=sorted(set(search_sources)),
                time_seconds=time.time() - start,
            )

            # 3. 发送概念+摘要结果（让用户立即看到部分结果）
            yield sse_retrieval_event(
                concepts=[_to_search_result(r, "keyword").model_dump() for r in concepts],
                summaries=[_to_search_result(r, "keyword").model_dump() for r in summaries],
                vector_results=[],
            )

            # 4. 向量检索（异步，通过 provider 抽象层）
            if mode in ("vector", "combined"):
                try:
                    vector_results = await asyncio.to_thread(vector_search, q, top_k, logger)
                    if vector_results:
                        search_sources.append("vector")
                        yield sse_retrieval_event(
                            concepts=[_to_search_result(r, "keyword").model_dump() for r in concepts],
                            summaries=[_to_search_result(r, "keyword").model_dump() for r in summaries],
                            vector_results=[_to_search_result(r, "vector").model_dump() for r in vector_results],
                        )
                except Exception as e:
                    logger.warning(f"Vector search failed: {e}")

            # 5. 流式生成 LLM 回答（异步）
            has_context = concepts or summaries or vector_results
            if not has_context:
                yield sse_answer_delta("未找到相关内容。请尝试其他关键词。")
                yield sse_done_event(time.time() - start, trace_id=get_current_trace_id())
                return

            provider = query_engine.create_query_provider(logger)
            if not provider:
                yield sse_answer_delta("（LLM 不可用，请检查 API 认证配置。）")
                yield sse_done_event(time.time() - start, trace_id=get_current_trace_id())
                return

            async for chunk in query_engine.generate_answer_stream_async(
                q, concepts, summaries, vector_results, provider, logger
            ):
                yield sse_answer_delta(chunk)

            yield sse_done_event(time.time() - start, trace_id=get_current_trace_id())

        except Exception as exc:
            logger.exception("流式查询失败")
            yield sse_error_event(str(exc))
            # 补发 done 事件，让客户端正常关闭流（避免永久 loading）
            yield sse_done_event(time.time() - start, trace_id=get_current_trace_id())

    return StreamingResponse(
        _async_generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
