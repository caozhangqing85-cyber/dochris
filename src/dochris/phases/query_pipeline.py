"""统一查询执行管线（QueryPipeline）。

普通查询（GET /query、CLI）与流式查询（GET /query/stream SSE）共用同一套
retrieve → rerank → context → generate 编排，避免两套代码行为漂移。

设计要点：
- 回调注入：检索/重排/provider/生成函数在请求时从 phase3_query / query_engine
  模块解析后传入，保持既有测试 patch 面与 Provider 可替换性（QRY-01/02/04）。
- 结构化事件：stream() 产出 PipelineEvent（meta/retrieval/rerank/warning/
  answer_delta/done），SSE 路由只做协议映射（QRY-05）。
- 流式一致性：done 事件携带清理后的 final_answer 与 citations，保证与非流式
  最终文本一致（QRY-06/07/08）。
- 类型化错误：QueryPipelineError(code)，vector 模式失败不吞错；combined 模式
  发出 warning 降级事件（QRY-09）。
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from dochris.core.error_sanitizer import sanitize_error_text
from dochris.observability.tracing import span
from dochris.rag.schemas import SourceRef

# 无事件时发送 SSE ping 的间隔（秒）
PING_INTERVAL_SECONDS = 15.0

_NO_CONTEXT_ANSWER = "未找到相关内容。请尝试其他关键词。"
_LLM_UNAVAILABLE_ANSWER = "（LLM 不可用，请检查 API 认证配置。）"


class QueryPipelineError(RuntimeError):
    """查询管线类型化错误。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(slots=True)
class PipelineEvent:
    """管线结构化事件。"""

    name: str
    """meta / retrieval / rerank / warning / answer_delta / done"""

    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PipelineCallbacks:
    """查询管线依赖注入点。

    所有可替换组件都以回调形式注入；调用方在请求时解析模块属性，
    保证 monkeypatch 与 Provider 注册表切换都能生效。
    """

    retrieve: Callable[..., dict[str, Any]]
    """(query, mode, top_k, logger, **kwargs) -> 检索结果 dict"""

    provider_factory: Callable[..., Any | None]
    """(logger) -> BaseLLMProvider | None"""

    generate: Callable[..., Awaitable[str | None]] | None = None
    """非流式生成：generate_async(query, concepts, summaries, vectors, provider, logger, context=...)"""

    generate_stream: Callable[..., AsyncIterator[str]] | None = None
    """流式生成：generate_stream(query, concepts, summaries, vectors, provider, logger, context=...)"""

    rerank: Callable[..., dict[str, Any]] | None = None
    """(query, result, top_k, logger) -> 重排后的检索结果 dict"""

    logger: logging.Logger | None = None

    def resolved_logger(self) -> logging.Logger:
        return self.logger or logging.getLogger("query_pipeline")


_CITATION_RE = re.compile(r"\[S(\d+)\]")


def extract_citations(
    answer: str,
    source_map: dict[str, SourceRef],
) -> tuple[list[dict[str, Any]], list[str]]:
    """从回答中解析 [Sn] 引用并映射到来源。

    Returns:
        (citations, unresolved_refs):
          - citations: 去重后的引用列表（按首次出现顺序），
            每项含 ref/manifest_id/source/channel/text_hash/score
          - unresolved_refs: 引用了但不存在于 source_map 的编号
    """
    citations: list[dict[str, Any]] = []
    seen: set[str] = set()
    unresolved: list[str] = []
    for match in _CITATION_RE.finditer(answer):
        ref = f"S{match.group(1)}"
        source_ref = source_map.get(ref)
        if source_ref is None:
            if ref not in unresolved:
                unresolved.append(ref)
            continue
        if ref in seen:
            continue
        seen.add(ref)
        citations.append(
            {
                "ref": ref,
                "manifest_id": source_ref.manifest_id,
                "source": source_ref.source,
                "channel": source_ref.channel,
                "text_hash": source_ref.text_hash,
                "score": source_ref.score,
            }
        )
    return citations, unresolved


class QueryPipeline:
    """只读查询统一编排：retrieve → rerank → context → generate。"""

    def __init__(self, callbacks: PipelineCallbacks) -> None:
        self._cb = callbacks

    # --------------------------------------------------------------
    # 共享阶段
    # --------------------------------------------------------------

    async def _retrieve(
        self,
        query: str,
        mode: str,
        top_k: int,
    ) -> tuple[dict[str, Any], str | None]:
        """执行检索，返回 (结果, 降级警告)。

        - mode=vector：失败直接抛 QueryPipelineError("vector_unavailable")。
        - 其他模式：向量失败降级为仅关键词检索，返回 warning 消息。
        """
        logger = self._cb.resolved_logger()
        try:
            with span("query.retrieve", mode=mode, top_k=top_k):
                result = await asyncio.to_thread(
                    self._cb.retrieve, query, mode, top_k, logger, vector_raise_on_error=True
                )
            return result, None
        except QueryPipelineError:
            raise
        except Exception as exc:
            if mode == "vector":
                raise QueryPipelineError(
                    "vector_unavailable",
                    f"向量检索失败: {sanitize_error_text(str(exc))}",
                ) from exc
            warning = f"向量检索不可用，已降级为关键词检索: {sanitize_error_text(str(exc))}"
            logger.warning("%s", warning)
            with span("query.retrieve_fallback", mode=mode):
                result = await asyncio.to_thread(
                    self._cb.retrieve,
                    query,
                    mode,
                    top_k,
                    logger,
                    vector_raise_on_error=False,
                    include_vector=False,
                )
            return result, warning

    async def _rerank(self, query: str, result: dict[str, Any], top_k: int) -> dict[str, Any]:
        if self._cb.rerank is None:
            return result
        with span("query.rerank", top_k=top_k):
            return await asyncio.to_thread(
                self._cb.rerank, query, result, top_k, self._cb.resolved_logger()
            )

    def _context_and_whitelist(
        self, query: str, result: dict[str, Any]
    ) -> tuple[str, dict[str, SourceRef], set[str]]:
        """构建上下文、来源映射与 wiki-link 白名单（与非流式生成完全一致）。"""
        from dochris.phases.query_engine import (
            build_answer_context,
            build_answer_prompt,
        )

        context, source_map = build_answer_context(
            result.get("concepts", []),
            result.get("summaries", []),
            result.get("vector_results", []),
        )
        _, _, all_known = build_answer_prompt(context, query, result.get("concepts", []))
        return context, source_map, all_known

    @staticmethod
    def _phase_timings(
        start: float,
        *,
        retrieval: float | None,
        rerank: float | None,
        first_token: float | None,
        generation: float | None,
    ) -> dict[str, float]:
        timings = {"total_seconds": round(time.perf_counter() - start, 2)}
        if retrieval is not None:
            timings["retrieval_seconds"] = round(retrieval, 2)
        if rerank is not None:
            timings["rerank_seconds"] = round(rerank, 2)
        if first_token is not None:
            timings["first_token_seconds"] = round(first_token, 2)
        if generation is not None:
            timings["generation_seconds"] = round(generation, 2)
        return timings

    # --------------------------------------------------------------
    # 非流式
    # --------------------------------------------------------------

    async def run(
        self,
        query: str,
        mode: str = "combined",
        top_k: int = 5,
        *,
        rerank: bool = False,
        trace_id: str = "",
    ) -> dict[str, Any]:
        """执行完整查询并返回结果 dict（含 citations/timings）。"""
        logger = self._cb.resolved_logger()
        start = time.perf_counter()
        result: dict[str, Any] = {
            "query": query,
            "mode": mode,
            "concepts": [],
            "summaries": [],
            "vector_results": [],
            "search_sources": [],
            "answer": None,
            "time_seconds": 0,
            "citations": [],
            "unresolved_refs": [],
            "timings": {},
        }
        if trace_id:
            result["trace_id"] = trace_id

        retrieval_start = time.perf_counter()
        retrieval, warning = await self._retrieve(query, mode, top_k)
        result.update(retrieval)
        retrieval_seconds = time.perf_counter() - retrieval_start
        if warning:
            result["warnings"] = [warning]

        rerank_seconds: float | None = None
        if rerank and self._cb.rerank is not None:
            rerank_start = time.perf_counter()
            result = {**result, **await self._rerank(query, result, top_k)}
            rerank_seconds = time.perf_counter() - rerank_start

        has_context = bool(
            result.get("concepts") or result.get("summaries") or result.get("vector_results")
        )
        if mode in ("combined", "all") and has_context:
            context, source_map, _ = self._context_and_whitelist(query, result)
            provider = self._cb.provider_factory(logger)
            if provider is not None and self._cb.generate is not None:
                with span("query.generate", mode=mode):
                    answer = await self._cb.generate(
                        query,
                        result.get("concepts", []),
                        result.get("summaries", []),
                        result.get("vector_results", []),
                        provider,
                        logger,
                        context=context,
                    )
            else:
                answer = _LLM_UNAVAILABLE_ANSWER
                logger.warning("LLM provider 不可用，仅返回检索结果")
            if answer:
                result["answer"] = answer
            citations, unresolved = extract_citations(result["answer"] or "", source_map)
            result["citations"] = citations
            result["unresolved_refs"] = unresolved

        result["timings"] = self._phase_timings(
            start,
            retrieval=retrieval_seconds,
            rerank=rerank_seconds,
            first_token=None,
            generation=None,
        )
        result["time_seconds"] = result["timings"]["total_seconds"]
        return result

    # --------------------------------------------------------------
    # 流式
    # --------------------------------------------------------------

    async def stream(
        self,
        query: str,
        mode: str = "combined",
        top_k: int = 5,
        *,
        rerank: bool = False,
        trace_id: str = "",
    ) -> AsyncIterator[PipelineEvent]:
        """以结构化事件流执行同一管线。

        错误通过 QueryPipelineError / TimeoutError 抛出，由传输层
        （SSE 路由）映射为 error 事件；取消（CancelledError）直接传播。
        """
        logger = self._cb.resolved_logger()
        start = time.perf_counter()
        retrieval_seconds: float | None = None
        rerank_seconds: float | None = None
        first_token_seconds: float | None = None
        generation_seconds: float | None = None

        retrieval_start = time.perf_counter()
        result, warning = await self._retrieve(query, mode, top_k)
        retrieval_seconds = time.perf_counter() - retrieval_start

        yield PipelineEvent(
            "meta",
            {
                "query": query,
                "mode": mode,
                "search_sources": list(result.get("search_sources", [])),
                "time_seconds": time.perf_counter() - start,
            },
        )
        if warning:
            yield PipelineEvent("warning", {"message": warning, "code": "vector_degraded"})
        yield PipelineEvent(
            "retrieval",
            {
                "concepts": result.get("concepts", []),
                "summaries": result.get("summaries", []),
                "vector_results": result.get("vector_results", []),
            },
        )

        if rerank and self._cb.rerank is not None:
            rerank_start = time.perf_counter()
            reranked = await self._rerank(query, result, top_k)
            rerank_seconds = time.perf_counter() - rerank_start
            if "reranker" in reranked.get("search_sources", []):
                result = reranked
                yield PipelineEvent(
                    "rerank",
                    {
                        "result_count": len(result.get("concepts", []))
                        + len(result.get("summaries", []))
                        + len(result.get("vector_results", [])),
                    },
                )
                yield PipelineEvent(
                    "retrieval",
                    {
                        "concepts": result.get("concepts", []),
                        "summaries": result.get("summaries", []),
                        "vector_results": result.get("vector_results", []),
                    },
                )

        has_context = bool(
            result.get("concepts") or result.get("summaries") or result.get("vector_results")
        )
        context, source_map, whitelist = (
            self._context_and_whitelist(query, result) if has_context else ("", {}, set())
        )

        final_answer = ""
        if not has_context:
            final_answer = _NO_CONTEXT_ANSWER
            yield PipelineEvent("answer_delta", {"text": final_answer})
        else:
            provider = self._cb.provider_factory(logger)
            if provider is None or self._cb.generate_stream is None:
                final_answer = _LLM_UNAVAILABLE_ANSWER
                yield PipelineEvent("answer_delta", {"text": final_answer})
            else:
                chunks: list[str] = []
                generation_start = time.perf_counter()
                async for chunk in self._cb.generate_stream(
                    query,
                    result.get("concepts", []),
                    result.get("summaries", []),
                    result.get("vector_results", []),
                    provider,
                    logger,
                    context=context,
                ):
                    if first_token_seconds is None:
                        first_token_seconds = time.perf_counter() - generation_start
                    chunks.append(chunk)
                    yield PipelineEvent("answer_delta", {"text": chunk})
                generation_seconds = time.perf_counter() - generation_start
                # 与非流式一致的后处理（wiki-link 白名单清理），保证最终文本一致
                from dochris.phases.query_engine import _sanitize_wiki_links

                final_answer = _sanitize_wiki_links("".join(chunks).strip(), whitelist)

        citations, unresolved = extract_citations(final_answer, source_map)
        done_timings = self._phase_timings(
            start,
            retrieval=retrieval_seconds,
            rerank=rerank_seconds,
            first_token=first_token_seconds,
            generation=generation_seconds,
        )
        yield PipelineEvent(
            "done",
            {
                "time_seconds": done_timings["total_seconds"],
                "timings": done_timings,
                "trace_id": trace_id,
                "final_answer": final_answer,
                "citations": citations,
                "unresolved_refs": unresolved,
            },
        )


async def stream_with_ping(
    events: AsyncIterator[PipelineEvent],
    *,
    interval: float = PING_INTERVAL_SECONDS,
) -> AsyncIterator[PipelineEvent | str]:
    """为事件流补充 ping 事件。

    单个事件超过 interval 秒未就绪时插入 ping（字符串 "ping"），
    传输层将其映射为 SSE ping 帧。

    实现说明：源事件流在独立 pump 任务中运行并写入队列。不能直接对
    `agen.__anext__()` 做 wait_for —— 超时会取消 __anext__ 协程并把
    CancelledError 注入生成器，导致源流被永久关闭（后续 ping 后再也
    取不到事件）。队列的 get 可以被安全地超时打断。
    """
    queue: asyncio.Queue[PipelineEvent | str | BaseException | None] = asyncio.Queue()

    async def _pump() -> None:
        try:
            async for event in events:
                await queue.put(event)
        except BaseException as exc:  # noqa: BLE001 - 需要把 CancelledError 之外的一切传给消费端
            await queue.put(exc)
        finally:
            await queue.put(None)

    pump_task = asyncio.create_task(_pump(), name="query-pipeline-ping-pump")
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=interval)
            except TimeoutError:  # asyncio.TimeoutError 在 3.11+ 为内建别名
                yield "ping"
                continue
            if item is None:
                return
            if isinstance(item, BaseException):
                raise item
            yield item
    finally:
        pump_task.cancel()
        try:
            await pump_task
        except (asyncio.CancelledError, Exception):
            pass
