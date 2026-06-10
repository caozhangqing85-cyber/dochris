"""Prometheus 指标端点 — GET /metrics"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from dochris.observability.metrics import generate_metrics
from dochris.settings import get_settings

router = APIRouter(tags=["monitoring"])


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    include_in_schema=False,
)
async def metrics() -> PlainTextResponse:
    """Prometheus 指标端点。

    仅在 PROMETHEUS_ENABLED=true 时返回指标数据，
    否则返回 404。
    """
    settings = get_settings()
    if settings.prometheus_enabled != "true":
        return PlainTextResponse("prometheus disabled", status_code=404)

    content = generate_metrics()
    return PlainTextResponse(
        content=content,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
