"""纯 ASGI 中间件 — trace_id 注入

执行顺序：CORS → tracing middleware → auth → route handler
确保所有请求（包括认证失败的）都有 trace_id。

使用纯 ASGI 实现（不继承 BaseHTTPMiddleware），
因为 BaseHTTPMiddleware 会缓存 StreamingResponse body，
破坏 SSE 流式语义。

用法（在 app.py 中）：
    from dochris.observability.middleware import TracingMiddleware
    app.add_middleware(TracingMiddleware)
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from dochris.observability.tracing import generate_trace_id, trace_request

logger = logging.getLogger(__name__)

# ASGI 类型别名
Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


class TracingMiddleware:
    """纯 ASGI 中间件，为每个 HTTP 请求注入 trace_id。

    - 在请求开始时生成 trace_id 并设置到 contextvars
    - 在响应头中返回 X-Trace-Id
    - 记录请求延迟（使用 monotonic 时钟）
    - 不缓存响应体，兼容 StreamingResponse / SSE
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        trace_id = generate_trace_id()

        with trace_request(trace_id):
            start = time.monotonic()
            header_injected = False

            async def send_with_trace(message: dict[str, Any]) -> None:
                nonlocal header_injected
                # 在第一个响应消息（http.response.start）中注入 trace_id
                if message["type"] == "http.response.start" and not header_injected:
                    headers = list(message.get("headers", []))
                    headers.append((b"x-trace-id", trace_id.encode()))
                    message["headers"] = headers
                    header_injected = True
                await send(message)

            await self.app(scope, receive, send_with_trace)
            latency = time.monotonic() - start

            logger.debug(
                "request: %s %s trace_id=%s latency=%.3fs",
                scope.get("method", "?"),
                scope.get("path", "?"),
                trace_id,
                latency,
            )
