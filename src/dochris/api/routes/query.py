"""查询路由 — GET /api/v1/query, GET /api/v1/query/stream

两个端点都通过 QueryPipeline 执行同一套 retrieve → rerank → context →
generate 编排；路由层只负责协议映射（JSON 响应 / SSE 事件）。
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from dochris.api.schemas import Citation, ErrorResponse, QueryResponse, SearchResult
from dochris.observability.tracing import get_current_trace_id
from dochris.phases import query_engine
from dochris.phases.phase3_query import query_async as do_query_async
from dochris.phases.query_pipeline import (
    QueryPipelineError,
    stream_with_ping,
)
from dochris.rag.schemas import normalize_score

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
        default=False,
        deprecated=True,
        description="已弃用；GET 查询始终只读，请使用 POST /query/contribution",
    ),
    rerank: bool = Query(default=False, description="启用 Reranker 重排序"),
) -> QueryResponse:
    """查询知识库

    支持概念搜索、摘要搜索、向量检索和综合查询。
    此 GET 端点始终只读。写入候选区请使用 POST /query/contribution。
    """
    if contribute:
        logger.info("忽略 GET /query 的已弃用 contribute 参数；查询保持只读")

    try:
        result = await do_query_async(
            q,
            mode=mode,
            top_k=top_k,
            logger=logger,
            contribute=False,
            workspace_path=None,
            rerank=rerank,
        )
    except QueryPipelineError as exc:
        logger.warning("查询类型化失败 (%s): %s", exc.code, exc.message)
        raise HTTPException(status_code=503, detail=f"{exc.code}: {exc.message}") from exc
    except Exception as exc:
        logger.exception("查询失败")
        # 与 SSE 链路对齐：不向浏览器透传内部异常细节，凭 trace_id 关联日志
        raise HTTPException(
            status_code=500,
            detail=f"查询失败，请查看服务端日志（trace_id={get_current_trace_id() or '无'}）",
        ) from exc

    return QueryResponse(
        query=result["query"],
        mode=result["mode"],
        concepts=[_to_search_result(r, "keyword") for r in result.get("concepts", [])],
        summaries=[_to_search_result(r, "keyword") for r in result.get("summaries", [])],
        vector_results=[_to_search_result(r, "vector") for r in result.get("vector_results", [])],
        search_sources=result.get("search_sources", []),
        answer=result.get("answer"),
        time_seconds=result.get("time_seconds", 0.0),
        reranked="reranker" in result.get("search_sources", []),
        citations=[
            Citation(**item)
            for item in result.get("citations", [])  # type: ignore[misc]
        ],
        unresolved_refs=result.get("unresolved_refs", []),
        warnings=result.get("warnings", []),
        llm_unavailable=bool(result.get("llm_unavailable", False)),
        timings=result.get("timings", {}),
        trace_id=get_current_trace_id(),
    )


@router.get(
    "/query/stream",
    responses={500: {"model": ErrorResponse}},
)
async def query_stream(
    q: str = Query(..., min_length=1, max_length=500, description="查询关键词"),
    mode: str = Query(default="combined", description="查询模式"),
    top_k: int = Query(default=5, ge=1, le=50, description="返回结果数量"),
    rerank: bool = Query(default=False, description="启用 Reranker 重排序"),
    contribute: bool = Query(default=False, description="启用 Query-as-Contribution"),
) -> StreamingResponse:
    """流式查询知识库 — SSE 端点

    与 GET /query 共用 QueryPipeline 编排。事件顺序：
    meta → (warning) → retrieval → (rerank + retrieval) → answer_delta* → done。

    SSE 事件格式 (v=1):
    - event: meta         — 查询元信息 (query, mode, search_sources)
    - event: warning      — 非致命降级（如 combined 模式向量检索不可用）
    - event: retrieval    — 检索结果 JSON (concepts + summaries + vector_results)
    - event: rerank       — 已应用 Reranker
    - event: answer_delta — LLM 回答的一个文本 chunk
    - event: done         — 流结束（含 final_answer / citations / timings / trace_id）
    - event: error        — 类型化错误信息
    - event: ping         — 心跳保活（生成期间每 15s）
    """
    if contribute:
        logger.info("忽略 GET /query/stream 的已弃用 contribute 参数；查询保持只读")

    async def _async_generate() -> Any:
        from dochris.api.sse import (
            sse_answer_delta,
            sse_done_event,
            sse_error_event,
            sse_meta_event,
            sse_ping_event,
            sse_rerank_event,
            sse_retrieval_event,
            sse_warning_event,
        )
        from dochris.phases import phase3_query
        from dochris.phases.query_pipeline import PipelineCallbacks, QueryPipeline

        start = time.perf_counter()

        def phase_timings() -> dict[str, float]:
            return {"total_seconds": round(time.perf_counter() - start, 2)}

        # 回调在请求时从模块解析，保持 Provider 可替换与既有测试 patch 面
        pipeline = QueryPipeline(
            PipelineCallbacks(
                retrieve=phase3_query.retrieve_query_context,
                rerank=phase3_query.rerank_query_context,
                provider_factory=query_engine.create_query_provider,
                generate_stream=query_engine.generate_answer_stream_async,
                logger=logger,
            )
        )

        def _dump_retrieval(data: dict[str, Any]) -> dict[str, Any]:
            return {
                "concepts": [
                    _to_search_result(r, "keyword").model_dump() for r in data.get("concepts", [])
                ],
                "summaries": [
                    _to_search_result(r, "keyword").model_dump() for r in data.get("summaries", [])
                ],
                "vector_results": [
                    _to_search_result(r, "vector").model_dump()
                    for r in data.get("vector_results", [])
                ],
            }

        try:
            events = stream_with_ping(
                pipeline.stream(q, mode, top_k, rerank=rerank, trace_id=get_current_trace_id())
            )
            async for event in events:
                if isinstance(event, str):
                    # ping 心跳
                    yield sse_ping_event()
                    continue
                if event.name == "meta":
                    yield sse_meta_event(
                        query=event.data["query"],
                        mode=event.data["mode"],
                        search_sources=sorted(set(event.data["search_sources"])),
                        time_seconds=event.data["time_seconds"],
                    )
                elif event.name == "warning":
                    yield sse_warning_event(
                        event.data["message"],
                        code=event.data.get("code", "warning"),
                    )
                elif event.name == "retrieval":
                    yield sse_retrieval_event(**_dump_retrieval(event.data))
                elif event.name == "rerank":
                    yield sse_rerank_event(event.data["result_count"])
                elif event.name == "answer_delta":
                    yield sse_answer_delta(event.data["text"])
                elif event.name == "done":
                    yield sse_done_event(
                        event.data["time_seconds"],
                        trace_id=event.data.get("trace_id") or get_current_trace_id(),
                        timings=event.data.get("timings"),
                        final_answer=event.data.get("final_answer"),
                        citations=event.data.get("citations"),
                        unresolved_refs=event.data.get("unresolved_refs"),
                        llm_unavailable=bool(event.data.get("llm_unavailable", False)),
                    )

        except asyncio.CancelledError:
            raise
        except QueryPipelineError as exc:
            logger.warning("流式查询类型化失败 (%s): %s", exc.code, exc.message)
            yield sse_error_event(
                exc.message,
                code=exc.code,
                terminal=True,
                trace_id=get_current_trace_id(),
                timings=phase_timings(),
            )
        except TimeoutError:
            logger.warning("流式查询超时")
            yield sse_error_event(
                "Query stream timed out.",
                code="timeout",
                terminal=True,
                trace_id=get_current_trace_id(),
                timings=phase_timings(),
            )
        except Exception:
            logger.exception("流式查询失败")
            yield sse_error_event(
                "Query stream failed.",
                code="stream_error",
                terminal=True,
                trace_id=get_current_trace_id(),
                timings=phase_timings(),
            )

    return StreamingResponse(
        _async_generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
