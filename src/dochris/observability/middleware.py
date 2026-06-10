"""FastAPI 中间件 — trace_id 注入

执行顺序：CORS → tracing middleware → auth → route handler
确保所有请求（包括认证失败的）都有 trace_id。

用法（在 app.py 中）：
    from dochris.observability.middleware import TracingMiddleware
    app.add_middleware(TracingMiddleware)
"""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from dochris.observability.tracing import generate_trace_id, trace_request

logger = logging.getLogger(__name__)


class TracingMiddleware(BaseHTTPMiddleware):
    """为每个 HTTP 请求注入 trace_id。

    - 在请求开始时生成 trace_id 并设置到 contextvars
    - 在响应头中返回 X-Trace-Id
    - 记录请求延迟
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        trace_id = generate_trace_id()

        with trace_request(trace_id):
            start = time.time()
            response = await call_next(request)
            latency = time.time() - start

            # 在响应头中返回 trace_id
            response.headers["X-Trace-Id"] = trace_id

            logger.debug(
                "request: %s %s trace_id=%s latency=%.3fs status=%d",
                request.method,
                request.url.path,
                trace_id,
                latency,
                response.status_code,
            )

            return response
