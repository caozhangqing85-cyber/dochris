"""Prometheus 指标端点 — GET /metrics"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from dochris.observability.metrics import generate_metrics
from dochris.settings import get_settings

router = APIRouter(tags=["monitoring"])

# /metrics 暴露业务情报（token 用量/延迟/调用次数），默认仅允许本地访问。
# 生产环境如需远程抓取，应通过反向代理加认证，而非直接暴露此端点。
_ALLOWED_METRICS_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    include_in_schema=False,
)
async def metrics(request: Request) -> PlainTextResponse:
    """Prometheus 指标端点。

    仅在 PROMETHEUS_ENABLED=true 且请求来自本地时返回指标数据，
    否则返回 404/403。
    """
    settings = get_settings()
    if settings.prometheus_enabled != "true":
        return PlainTextResponse("prometheus disabled", status_code=404)

    # 仅允许本地访问，防止业务指标泄露
    client_info = getattr(request, "client", None)
    client_host = client_info.host if client_info else ""
    if client_host not in _ALLOWED_METRICS_HOSTS:
        raise HTTPException(
            status_code=403,
            detail="Metrics endpoint only accessible from localhost. "
            "Use a reverse proxy with auth for remote scraping.",
        )

    content = generate_metrics()
    return PlainTextResponse(
        content=content,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
