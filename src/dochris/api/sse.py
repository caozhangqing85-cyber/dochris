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
        # splitlines 处理 \n / \r\n / \r 三种换行符，避免 \r 破坏事件帧
        lines = data.splitlines()
        if lines:
            parts.extend(f"data: {line}" for line in lines)
        else:
            parts.append("data: ")
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


def sse_answer_delta(text: str) -> str:
    """构建 answer_delta 事件。"""
    return sse_encode(QueryStreamEventName.ANSWER_DELTA, text)


def sse_done_event(time_seconds: float, trace_id: str = "") -> str:
    """构建 done 事件。"""
    data: dict[str, Any] = {
        "v": SSE_EVENT_VERSION,
        "time_seconds": round(time_seconds, 2),
    }
    if trace_id:
        data["trace_id"] = trace_id
    return sse_encode(QueryStreamEventName.DONE, data)


def sse_error_event(message: str) -> str:
    """构建 error 事件。"""
    return sse_encode(
        QueryStreamEventName.ERROR,
        {"v": SSE_EVENT_VERSION, "message": message},
    )


def sse_ping_event() -> str:
    """构建 ping 心跳事件。"""
    return sse_encode(QueryStreamEventName.PING, {"v": SSE_EVENT_VERSION})
