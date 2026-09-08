"""SSE 事件编码与类型定义

定义查询流式输出的标准事件格式，替代裸字符串。
使用 StrEnum 与项目 types.py 中的 FileStatus/FileType 惯例一致。

事件类型：
- meta: 查询元信息（query, mode, search_sources）
- retrieval: 检索结果（concepts + summaries + vector_results）
- rerank: 重排序结果
- answer_delta: LLM 回答的一个文本片段
- done: 流结束
- error: 错误信息
- ping: 心跳保活

用法：
    async for event in stream_query_events(query, mode, top_k):
        yield sse_encode(event)
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

# 事件 schema 版本
SSE_EVENT_VERSION = 1


class QueryStreamEventName(StrEnum):
    """查询流式事件名。"""

    META = "meta"
    RETRIEVAL = "retrieval"
    RERANK = "rerank"
    WARNING = "warning"
    ANSWER_DELTA = "answer_delta"
    DONE = "done"
    ERROR = "error"
    PING = "ping"


def sse_encode(
    event: str,
    data: Any = None,
    event_id: str | None = None,
) -> str:
    """编码为 SSE 文本格式。

    格式：
        event: <name>\\n
        data: <json>\\n
        \\n

    Args:
        event: 事件名称
        data: 事件数据（dict/list/str）
        event_id: 可选的事件 ID

    Returns:
        SSE 格式字符串
    """
    parts: list[str] = []

    if event_id:
        parts.append(f"id: {event_id}")

    parts.append(f"event: {event}")

    if isinstance(data, (dict, list)):
        payload = json.dumps(data, ensure_ascii=False)
        parts.append(f"data: {payload}")
    elif isinstance(data, str):
        # SSE 协议：多行内容必须拆为多个 data: 行。
        # 只按 \n 拆分（先归一化 \r\n、\r），保留尾随换行与 U+2028 等字符，
        # 避免增量文本与最终答案漂移
        normalized = data.replace("\r\n", "\n").replace("\r", "\n")
        lines = normalized.split("\n")
        parts.extend(f"data: {line}" for line in lines)
    elif data is not None:
        parts.append(f"data: {data}")
    else:
        parts.append("data: ")
    parts.append("")  # 空行结束事件

    return "\n".join(parts) + "\n"


def sse_meta_event(
    query: str,
    mode: str,
    search_sources: list[str],
    time_seconds: float = 0.0,
) -> str:
    """构建 meta 事件。"""
    return sse_encode(
        QueryStreamEventName.META,
        {
            "v": SSE_EVENT_VERSION,
            "query": query,
            "mode": mode,
            "search_sources": search_sources,
            "time_seconds": round(time_seconds, 2),
        },
    )


def sse_retrieval_event(
    concepts: list[dict],
    summaries: list[dict],
    vector_results: list[dict],
) -> str:
    """构建 retrieval 事件。"""
    return sse_encode(
        QueryStreamEventName.RETRIEVAL,
        {
            "v": SSE_EVENT_VERSION,
            "concepts": concepts,
            "summaries": summaries,
            "vector_results": vector_results,
        },
    )


def sse_rerank_event(reranked_count: int) -> str:
    """构建已应用 Reranker 的阶段事件。"""
    return sse_encode(
        QueryStreamEventName.RERANK,
        {
            "v": SSE_EVENT_VERSION,
            "reranked": True,
            "result_count": reranked_count,
        },
    )


def sse_warning_event(
    message: str,
    *,
    code: str = "warning",
) -> str:
    """构建非致命 warning 事件（如 combined 模式向量降级）。"""
    return sse_encode(
        QueryStreamEventName.WARNING,
        {"v": SSE_EVENT_VERSION, "message": message, "code": code},
    )


def sse_answer_delta(text: str) -> str:
    """构建 answer_delta 事件。"""
    return sse_encode(QueryStreamEventName.ANSWER_DELTA, text)


def sse_done_event(
    time_seconds: float,
    trace_id: str = "",
    contribution: dict[str, Any] | None = None,
    timings: dict[str, float] | None = None,
    final_answer: str | None = None,
    citations: list[dict[str, Any]] | None = None,
    unresolved_refs: list[str] | None = None,
    llm_unavailable: bool = False,
) -> str:
    """构建 done 事件。

    final_answer 是与非流式一致的后处理答案；前端应在收到 done 时用其
    替换增量渲染的文本，保证两种模式最终答案完全一致。
    llm_unavailable 表示生成通道不可用，answer 为降级提示而非真实回答。
    """
    data: dict[str, Any] = {
        "v": SSE_EVENT_VERSION,
        "time_seconds": round(time_seconds, 2),
    }
    if timings:
        data["timings"] = timings
    if trace_id:
        data["trace_id"] = trace_id
    if contribution:
        data["contribution"] = contribution
    if final_answer is not None:
        data["final_answer"] = final_answer
    if citations is not None:
        data["citations"] = citations
    if unresolved_refs is not None:
        data["unresolved_refs"] = unresolved_refs
    if llm_unavailable:
        data["llm_unavailable"] = True
    return sse_encode(QueryStreamEventName.DONE, data)


def sse_error_event(
    message: str,
    *,
    code: str = "stream_error",
    terminal: bool = True,
    trace_id: str = "",
    timings: dict[str, float] | None = None,
) -> str:
    """构建 error 事件。"""
    data: dict[str, Any] = {
        "v": SSE_EVENT_VERSION,
        "message": message,
        "code": code,
        "terminal": terminal,
    }
    if trace_id:
        data["trace_id"] = trace_id
    if timings:
        data["timings"] = timings
    return sse_encode(QueryStreamEventName.ERROR, data)


def sse_ping_event() -> str:
    """构建 ping 心跳事件。"""
    return sse_encode(QueryStreamEventName.PING, {"v": SSE_EVENT_VERSION})
