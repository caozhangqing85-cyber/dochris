"""查询路由 — GET /api/v1/query, GET /api/v1/query/stream"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from dochris.api.schemas import ErrorResponse, QueryResponse, SearchResult
from dochris.phases.phase3_query import query as do_query
from dochris.phases import query_engine
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
) -> QueryResponse:
    """查询知识库

    支持概念搜索、摘要搜索、向量检索和综合查询。
    当 contribute=true 时，高质量回答会自动写入候选区（outputs/candidates/）。
    """
    settings = get_settings()
    workspace_path = settings.workspace

    try:
        result = do_query(
            q,
            mode=mode,
            top_k=top_k,
            logger=logger,
            contribute=contribute,
            workspace_path=workspace_path,
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
) -> StreamingResponse:
    """流式查询知识库 — SSE 端点

    先返回检索结果（concepts, summaries, vector_results），
    然后流式返回 LLM 生成的回答。

    SSE 事件格式:
    - event: meta        — 查询元信息 (query, mode, search_sources)
    - event: results     — 检索结果 JSON (concepts + summaries + vector_results)
    - event: answer      — LLM 回答的一个文本 chunk
    - event: done        — 流结束
    - event: error       — 错误信息
    """
    settings = get_settings()
    workspace_path = settings.workspace

    def _sse_event(event: str, data: Any) -> str:
        payload = json.dumps(data, ensure_ascii=False) if isinstance(data, (dict, list)) else str(data)
        return f"event: {event}\ndata: {payload}\n\n"

    def _generate() -> Any:
        try:
            # 1. 执行检索（非 LLM 部分）
            import time
            from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
            start = time.time()

            from dochris.phases.phase3_query import (
                search_concepts,
                search_summaries,
                vector_search,
                create_client,
            )

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
            yield _sse_event("meta", {
                "query": q, "mode": mode,
                "search_sources": sorted(set(search_sources)),
                "time_seconds": round(time.time() - start, 2),
            })

            # 3. 发送概念+摘要结果（让用户立即看到部分结果）
            yield _sse_event("results", {
                "concepts": [_to_search_result(r, "keyword").model_dump() for r in concepts],
                "summaries": [_to_search_result(r, "keyword").model_dump() for r in summaries],
                "vector_results": [],
            })

            # 4. 向量检索（可能耗时较长，加超时保护）
            if mode in ("vector", "combined"):
                executor = ThreadPoolExecutor(max_workers=1)
                try:
                    future = executor.submit(vector_search, q, top_k, logger)
                    vector_results = future.result(timeout=10)
                    if vector_results:
                        search_sources.append("vector")
                        # 发送补充的向量检索结果
                        yield _sse_event("results", {
                            "concepts": [_to_search_result(r, "keyword").model_dump() for r in concepts],
                            "summaries": [_to_search_result(r, "keyword").model_dump() for r in summaries],
                            "vector_results": [_to_search_result(r, "vector").model_dump() for r in vector_results],
                        })
                except FuturesTimeout:
                    logger.warning("Vector search timed out (10s), skipping")
                except Exception as e:
                    logger.warning(f"Vector search failed: {e}")
                finally:
                    executor.shutdown(wait=False, cancel_futures=True)

            # 5. 流式生成 LLM 回答
            has_context = concepts or summaries or vector_results
            if not has_context:
                yield _sse_event("answer", "未找到相关内容。请尝试其他关键词。")
                yield _sse_event("done", {"time_seconds": round(time.time() - start, 2)})
                return

            client = create_client(logger)
            if not client:
                yield _sse_event("answer", "（LLM 不可用，请检查 API 认证配置。）")
                yield _sse_event("done", {"time_seconds": round(time.time() - start, 2)})
                return

            for chunk in query_engine.generate_answer_stream(
                q, concepts, summaries, vector_results, client, logger
            ):
                yield _sse_event("answer", chunk)

            yield _sse_event("done", {"time_seconds": round(time.time() - start, 2)})

        except Exception as exc:
            logger.exception("流式查询失败")
            yield _sse_event("error", str(exc))

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
