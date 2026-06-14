"""Prometheus 指标注册表

定义查询、检索、LLM 调用的 Counter / Histogram / Gauge。
使用 prometheus_client 的默认 Registry，通过 /metrics 端点暴露。

设计原则：
- 默认关闭（PROMETHEUS_ENABLED=false），不注册任何指标
- 首次启用时注册，后续调用直接获取已注册指标
- 所有方法都有 fallback：metrics 不可用时静默跳过
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 全局注册锁，防止并发注册
_registry_lock = threading.Lock()
# _registered 定义见下方 _ensure_registered 前的三态声明


@dataclass(frozen=True)
class LLMUsage:
    """LLM 调用用量记录。"""

    provider: str
    """LLM 提供商（openai_compat / ollama）"""

    model: str
    """模型名称"""

    operation: str
    """操作类型（generate / generate_stream / generate_with_messages）"""

    prompt_tokens: int = 0
    """输入 token 数"""

    completion_tokens: int = 0
    """输出 token 数"""

    total_tokens: int = 0
    """总 token 数"""

    latency_ms: float = 0.0
    """请求延迟（毫秒）"""

    cost_usd: float | None = None
    """估算成本（USD）"""

    error_type: str | None = None
    """错误类型（如 rate_limit / timeout / content_filter）"""


# 注册状态三态：None=未尝试，True=成功，False=已失败（不重试，避免每次 record 都尝试）
_registered: bool | None = None


def _ensure_registered() -> bool:
    """确保 Prometheus 指标已注册。返回 True 表示可用。"""
    global _registered

    if _registered is True:
        return True
    if _registered is False:
        # 已失败过，不再重试（避免每次 record_* 都触发重复注册尝试）
        return False

    try:
        from prometheus_client import Counter  # noqa: F401 — 检测可用性
    except ImportError:
        _registered = False
        return False

    with _registry_lock:
        if _registered is True:
            return True
        if _registered is False:
            return False

        # 注册：_register_metrics 全部成功才标记 True
        try:
            _register_metrics()
            _registered = True
            return True
        except Exception as e:
            logger.warning("Prometheus 指标注册失败，可观测性记录将降级为空操作: %s", e)
            _registered = False
            return False


# 指标实例（延迟初始化）
_query_counter = None
_query_latency = None
_llm_counter = None
_llm_latency = None
_llm_tokens = None
_retrieval_counter = None
_retrieval_latency = None
_rerank_counter = None
_rerank_latency = None
_cache_counter = None


def _register_metrics() -> None:
    """注册所有 Prometheus 指标（只调用一次）。

    使用 try/except 防止热重载或测试场景下重复注册导致 ValueError。
    """
    global \
        _query_counter, _query_latency, \
        _llm_counter, _llm_latency, _llm_tokens, \
        _retrieval_counter, _retrieval_latency, \
        _rerank_counter, _rerank_latency, \
        _cache_counter

    from prometheus_client import Counter, Histogram

    try:
        _query_counter = Counter(
            "dochris_query_total",
            "Total number of queries",
            ["mode", "status"],
        )
        _query_latency = Histogram(
            "dochris_query_latency_seconds",
            "Query latency in seconds",
            ["mode"],
            buckets=[0.5, 1, 2, 5, 10, 30, 60],
        )
        _llm_counter = Counter(
            "dochris_llm_calls_total",
            "Total LLM API calls",
            ["provider", "model", "operation", "status"],
        )
        _llm_latency = Histogram(
            "dochris_llm_latency_seconds",
            "LLM API call latency in seconds",
            ["provider", "model"],
            buckets=[0.5, 1, 2, 5, 10, 30, 60, 120],
        )
        _llm_tokens = Counter(
            "dochris_llm_tokens_total",
            "Total LLM token usage",
            ["provider", "model", "type"],  # type: prompt / completion
        )
        _retrieval_counter = Counter(
            "dochris_retrieval_total",
            "Total retrieval operations",
            ["retriever", "status"],
        )
        _retrieval_latency = Histogram(
            "dochris_retrieval_latency_seconds",
            "Retrieval latency in seconds",
            ["retriever"],
            buckets=[0.1, 0.25, 0.5, 1, 2, 5],
        )
        _rerank_counter = Counter(
            "dochris_rerank_total",
            "Total rerank operations",
            ["provider", "status"],
        )
        _rerank_latency = Histogram(
            "dochris_rerank_latency_seconds",
            "Rerank latency in seconds",
            ["provider"],
            buckets=[0.1, 0.25, 0.5, 1, 2, 5],
        )
        _cache_counter = Counter(
            "dochris_cache_total",
            "Cache hit/miss counter",
            ["result"],  # result: hit / miss
        )
    except ValueError:
        # 热重载或测试场景下可能已注册，跳过重复注册
        logger.warning("Prometheus 指标已注册，跳过重复注册")


def record_query(mode: str, status: str = "success", latency: float = 0.0) -> None:
    """记录查询指标。"""
    if not _ensure_registered() or _query_counter is None:
        return
    _query_counter.labels(mode=mode, status=status).inc()
    if latency > 0 and _query_latency is not None:
        _query_latency.labels(mode=mode).observe(latency)


def record_llm_usage(usage: LLMUsage) -> None:
    """记录 LLM 调用指标。"""
    if not _ensure_registered() or _llm_counter is None:
        return
    status = usage.error_type or "success"
    _llm_counter.labels(
        provider=usage.provider,
        model=usage.model,
        operation=usage.operation,
        status=status,
    ).inc()
    if usage.latency_ms > 0 and _llm_latency is not None:
        _llm_latency.labels(
            provider=usage.provider, model=usage.model
        ).observe(usage.latency_ms / 1000.0)
    if usage.prompt_tokens > 0 and _llm_tokens is not None:
        _llm_tokens.labels(
            provider=usage.provider, model=usage.model, type="prompt"
        ).inc(usage.prompt_tokens)
    if usage.completion_tokens > 0 and _llm_tokens is not None:
        _llm_tokens.labels(
            provider=usage.provider, model=usage.model, type="completion"
        ).inc(usage.completion_tokens)


def record_retrieval(
    retriever: str,
    candidate_count: int = 0,
    latency: float = 0.0,
    status: str = "success",
) -> None:
    """记录检索指标。"""
    if not _ensure_registered() or _retrieval_counter is None:
        return
    _retrieval_counter.labels(retriever=retriever, status=status).inc()
    if latency > 0 and _retrieval_latency is not None:
        _retrieval_latency.labels(retriever=retriever).observe(latency)


def record_rerank(
    provider: str,
    input_count: int = 0,
    output_count: int = 0,
    latency: float = 0.0,
    status: str = "success",
) -> None:
    """记录 Rerank 指标。"""
    if not _ensure_registered() or _rerank_counter is None:
        return
    _rerank_counter.labels(provider=provider, status=status).inc()
    if latency > 0 and _rerank_latency is not None:
        _rerank_latency.labels(provider=provider).observe(latency)


def record_cache(result: str) -> None:
    """记录缓存命中/未命中。"""
    if not _ensure_registered() or _cache_counter is None:
        return
    _cache_counter.labels(result=result).inc()


def generate_metrics() -> str:
    """生成 Prometheus 文本格式指标输出。"""
    try:
        from prometheus_client import generate_latest

        return generate_latest().decode("utf-8")
    except ImportError:
        return ""
