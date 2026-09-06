"""可选 OpenTelemetry 导出（OBS-02）。

默认完全关闭、零依赖：只有同时满足
1. 安装了 ``opentelemetry`` SDK（``pip install dochris[otel]``）；
2. 环境变量 ``DOCHRIS_OTEL_ENABLED=true``；

才会把内部 span 桥接到 OpenTelemetry。配置了
``OTEL_EXPORTER_OTLP_ENDPOINT`` 时经 OTLP 导出，否则仅走默认处理器。

设计约束：任何导入失败/导出异常都必须静默降级，不得影响主流程。
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_TRUTHY = {"1", "true", "yes", "on"}
_ENABLED: bool | None = None


def otel_enabled() -> bool:
    """是否启用 OTel 桥接（结果进程内缓存）。"""
    global _ENABLED
    if _ENABLED is None:
        flag = os.environ.get("DOCHRIS_OTEL_ENABLED", "").strip().lower()
        if flag not in _TRUTHY:
            _ENABLED = False
            return False
        try:
            import opentelemetry.sdk  # noqa: F401
        except ImportError:
            logger.debug("DOCHRIS_OTEL_ENABLED 已开启，但 opentelemetry-sdk 未安装，桥接关闭")
            _ENABLED = False
            return False
        _ENABLED = True
    return _ENABLED


def reset_cache() -> None:
    """测试用：清空启用状态缓存。"""
    global _ENABLED
    _ENABLED = None


def export_span(
    name: str,
    trace_id: str,
    span_id: str,
    duration_ms: float,
    attributes: dict[str, Any] | None = None,
) -> bool:
    """把一个已完成的内部 span 桥接为 OTel span。

    Returns:
        是否真正导出（未启用/异常时 False）。
    """
    if not otel_enabled():
        return False
    try:
        import opentelemetry.trace as otel_trace
        from opentelemetry.trace import (
            NonRecordingSpan,
            SpanContext,
            TraceFlags,
            set_span_in_context,
        )

        tid_int = int(trace_id, 16) if trace_id else 0
        sid_int = int(span_id, 16) if span_id else 0
        if not tid_int or not sid_int:
            return False

        parent_span_context = SpanContext(
            trace_id=tid_int,
            span_id=sid_int,
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
        parent_context = set_span_in_context(NonRecordingSpan(parent_span_context))
        tracer = otel_trace.get_tracer("dochris")
        otel_span = tracer.start_span(name, context=parent_context)
        for key, value in (attributes or {}).items():
            try:
                otel_span.set_attribute(key[:200], value)
            except Exception:  # noqa: BLE001 - 单个属性失败不阻塞
                pass
        otel_span.end()
        return True
    except Exception:  # noqa: BLE001 - 观测失败绝不影响主流程
        logger.debug("OTel span 导出失败", exc_info=True)
        return False
