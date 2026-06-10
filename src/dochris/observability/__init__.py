"""可观测性模块 — 追踪、指标、成本估算

统一入口：ObservabilityManager 提供 span / record_llm_usage / record_retrieval 三个核心方法。
默认关闭（OBSERVABILITY_ENABLED=false），启用后自动注册 Prometheus 指标。

用法：
    from dochris.observability import get_observability

    obs = get_observability()
    with obs.span("retrieval", query="费曼技巧"):
        ...
    obs.record_llm_usage(LLMUsage(...))
"""

from collections.abc import Generator

from dochris.observability.cost import CostEstimator
from dochris.observability.metrics import (
    LLMUsage,
    generate_metrics,
    record_cache,
    record_llm_usage,
    record_query,
    record_rerank,
    record_retrieval,
)
from dochris.observability.tracing import (
    SpanContext,
    generate_trace_id,
    get_current_trace_id,
    span,
    trace_request,
)

__all__ = [
    "CostEstimator",
    "LLMUsage",
    "ObservabilityManager",
    "SpanContext",
    "generate_metrics",
    "generate_trace_id",
    "get_current_trace_id",
    "get_observability",
    "record_cache",
    "record_llm_usage",
    "record_query",
    "record_rerank",
    "record_retrieval",
    "span",
    "trace_request",
]


class ObservabilityManager:
    """统一观测入口。

    默认关闭时所有方法为空操作（no-op），零开销。
    启用后自动注册 Prometheus 指标并生成 trace_id。
    """

    def __init__(self, enabled: bool = False) -> None:
        self._enabled = enabled
        self._cost_estimator = CostEstimator()

    @property
    def enabled(self) -> bool:
        """是否启用可观测性。"""
        return self._enabled

    def span(self, name: str, **attrs: str | int | float) -> Generator[SpanContext, None, None]:
        """创建 trace span（上下文管理器）。

        即使 disabled 也返回有效的 context manager，不报错。
        """
        return span(name, **attrs)

    def record_llm_usage(self, usage: LLMUsage) -> None:
        """记录 LLM token、延迟、成本。"""
        if not self._enabled:
            return

        # 补充成本估算
        if usage.cost_usd is None:
            cost = self._cost_estimator.estimate(
                provider=usage.provider,
                model=usage.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
            )
            if cost is not None:
                usage = LLMUsage(
                    provider=usage.provider,
                    model=usage.model,
                    operation=usage.operation,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                    latency_ms=usage.latency_ms,
                    cost_usd=cost,
                    error_type=usage.error_type,
                )

        record_llm_usage(usage)

    def record_retrieval(
        self,
        query: str,
        candidate_count: int,
        latency_ms: float,
        collection_name: str | None = None,
        retriever_type: str | None = None,
    ) -> None:
        """记录检索指标。

        注意：query / collection_name 当前未传递给底层 metrics，
        保留签名供后续按查询/集合维度聚合使用。
        """
        if not self._enabled:
            return
        retriever = retriever_type or "unknown"
        record_retrieval(
            retriever=retriever,
            candidate_count=candidate_count,
            latency=latency_ms / 1000.0,
        )


# 全局单例
_instance: ObservabilityManager | None = None


def get_observability() -> ObservabilityManager:
    """获取全局 ObservabilityManager 实例。"""
    global _instance
    if _instance is None:
        from dochris.settings import get_settings

        settings = get_settings()
        enabled = settings.observability_enabled == "true"
        _instance = ObservabilityManager(enabled=enabled)
    return _instance


def reset_observability() -> None:
    """重置全局实例（主要用于测试）。"""
    global _instance
    _instance = None
