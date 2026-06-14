"""轻量级追踪 — trace_id/span_id 生成与上下文传播

不依赖 OpenTelemetry SDK（避免重依赖），使用 contextvars 传播 trace context。
每个 HTTP 请求自动生成 trace_id，内部操作（检索/rerank/LLM）创建子 span。

设计原则：
- 默认关闭（OBSERVABILITY_ENABLED=false），零开销
- SDK 错误不破坏应用逻辑
- trace_id 写入 API response，便于前端错误反馈关联后端日志
"""

from __future__ import annotations

import contextvars
import logging
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# 上下文变量：当前请求的 trace_id 和 span 栈
_current_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trace_id", default=""
)
_current_span_stack: contextvars.ContextVar[list[str]] = contextvars.ContextVar(
    "span_stack", default=None
)


def generate_trace_id() -> str:
    """生成 trace_id（32 字符 hex）。"""
    return uuid.uuid4().hex


def generate_span_id() -> str:
    """生成 span_id（16 字符 hex）。"""
    return uuid.uuid4().hex[:16]


def get_current_trace_id() -> str:
    """获取当前上下文的 trace_id。"""
    return _current_trace_id.get()


@dataclass(frozen=True)
class SpanContext:
    """Span 上下文信息。"""

    span_id: str
    trace_id: str


@contextmanager
def trace_request(trace_id: str | None = None) -> Generator[SpanContext, None, None]:
    """为一次 HTTP 请求创建 trace context。

    应在 API middleware 中调用，包裹整个请求处理过程。

    Args:
        trace_id: 可选的 trace_id，不提供则自动生成

    Yields:
        SpanContext 包含 trace_id 和根 span_id
    """
    tid = trace_id or generate_trace_id()
    token_trace = _current_trace_id.set(tid)
    # span_stack 用 token 记录，退出时 reset（而非 set(None) 污染父上下文）
    token_stack = _current_span_stack.set([])
    try:
        yield SpanContext(span_id=generate_span_id(), trace_id=tid)
    finally:
        _current_trace_id.reset(token_trace)
        _current_span_stack.reset(token_stack)


@contextmanager
def span(name: str, **attrs: Any) -> Generator[SpanContext, None, None]:
    """创建一个子 span。

    在 trace_request 上下文内使用，记录操作名称和属性。

    Args:
        name: span 名称（如 "retrieval", "llm_generate"）
        **attrs: span 属性（如 model="glm-5.1", tokens=1500）

    Yields:
        SpanContext 包含 span_id 和 trace_id
    """
    trace_id = _current_trace_id.get("")
    span_id = generate_span_id()

    if not trace_id:
        # 无 trace context（CLI 或测试环境），静默跳过
        yield SpanContext(span_id=span_id, trace_id="")
        return

    # 入栈
    stack = _current_span_stack.get(None)
    if stack is not None:
        stack.append(name)

    logger.debug(
        "span:start name=%s span_id=%s trace_id=%s attrs=%s",
        name, span_id, trace_id, attrs,
    )

    try:
        yield SpanContext(span_id=span_id, trace_id=trace_id)
    finally:
        if stack is not None and stack and stack[-1] == name:
            stack.pop()
        logger.debug("span:end name=%s span_id=%s", name, span_id)
