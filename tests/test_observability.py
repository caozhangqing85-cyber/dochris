#!/usr/bin/env python3
"""可观测性模块测试

覆盖：
- tracing: trace_id 生成、span 上下文传播
- metrics: Prometheus 指标注册、记录方法
- cost: LLM 成本估算
- SSE: 事件编码、类型枚举
- ObservabilityManager: enabled/disabled 行为
"""

from unittest import TestCase

from dochris.observability.cost import CostEstimator
from dochris.observability.metrics import (
    LLMUsage,
    generate_metrics,
)
from dochris.observability.tracing import (
    SpanContext,
    generate_span_id,
    generate_trace_id,
    get_current_trace_id,
    span,
    trace_request,
)

# ============================================================
# Tracing 测试
# ============================================================


class TestTracing(TestCase):
    """trace_id / span 上下文测试"""

    def test_generate_trace_id_format(self) -> None:
        """trace_id 是 32 字符 hex"""
        tid = generate_trace_id()
        self.assertEqual(len(tid), 32)
        self.assertTrue(all(c in "0123456789abcdef" for c in tid))

    def test_generate_span_id_format(self) -> None:
        """span_id 是 16 字符 hex"""
        sid = generate_span_id()
        self.assertEqual(len(sid), 16)

    def test_trace_request_sets_context(self) -> None:
        """trace_request 设置 trace_id 上下文"""
        with trace_request("test-trace-123") as ctx:
            self.assertEqual(ctx.trace_id, "test-trace-123")
            self.assertEqual(get_current_trace_id(), "test-trace-123")

    def test_trace_request_auto_generates_id(self) -> None:
        """不传 trace_id 时自动生成"""
        with trace_request() as ctx:
            self.assertEqual(len(ctx.trace_id), 32)

    def test_trace_request_cleans_up(self) -> None:
        """trace_request 退出后上下文清除"""
        with trace_request("temp-trace"):
            pass
        self.assertEqual(get_current_trace_id(), "")

    def test_span_within_trace(self) -> None:
        """span 在 trace_request 内工作"""
        with trace_request("outer-trace"):
            with span("retrieval", query="test") as s:
                self.assertEqual(s.trace_id, "outer-trace")
                self.assertEqual(len(s.span_id), 16)

    def test_span_without_trace_is_noop(self) -> None:
        """无 trace_request 时 span 静默跳过"""
        with span("orphan") as s:
            self.assertEqual(s.trace_id, "")


# ============================================================
# Cost Estimator 测试
# ============================================================


class TestCostEstimator(TestCase):
    """LLM 成本估算测试"""

    def setUp(self) -> None:
        self.estimator = CostEstimator()

    def test_known_model_exact_match(self) -> None:
        """精确匹配已知模型"""
        cost = self.estimator.estimate(
            provider="openai_compat",
            model="glm-4-flash",
            prompt_tokens=1000,
            completion_tokens=500,
        )
        # glm-4-flash: (0.0001, 0.0001)
        expected = 1.0 * 0.0001 + 0.5 * 0.0001  # 0.00015
        self.assertAlmostEqual(cost or 0, expected, places=6)

    def test_known_model_prefix_match(self) -> None:
        """前缀匹配模型（如 glm-5.1 匹配 glm-5）"""
        cost = self.estimator.estimate(
            provider="openai_compat",
            model="glm-5.1",
            prompt_tokens=1000,
            completion_tokens=0,
        )
        self.assertIsNotNone(cost)
        self.assertGreater(cost or 0, 0)

    def test_ollama_is_free(self) -> None:
        """Ollama 本地模型成本为 0"""
        cost = self.estimator.estimate(
            provider="ollama",
            model="qwen:14b",
            prompt_tokens=5000,
            completion_tokens=2000,
        )
        self.assertEqual(cost, 0.0)

    def test_unknown_model_returns_none(self) -> None:
        """未知模型返回 None"""
        cost = self.estimator.estimate(
            provider="unknown",
            model="mystery-model",
            prompt_tokens=100,
            completion_tokens=50,
        )
        self.assertIsNone(cost)


# ============================================================
# LLMUsage 数据类测试
# ============================================================


class TestLLMUsage(TestCase):
    """LLMUsage 数据结构测试"""

    def test_frozen_dataclass(self) -> None:
        """LLMUsage 是 frozen 的"""
        usage = LLMUsage(provider="test", model="m1", operation="gen")
        with self.assertRaises(AttributeError):
            usage.provider = "other"  # type: ignore[misc]

    def test_default_values(self) -> None:
        """默认值为零"""
        usage = LLMUsage(provider="test", model="m1", operation="gen")
        self.assertEqual(usage.prompt_tokens, 0)
        self.assertEqual(usage.completion_tokens, 0)
        self.assertIsNone(usage.cost_usd)
        self.assertIsNone(usage.error_type)


# ============================================================
# SSE 编码测试
# ============================================================


class TestSSEEncoding(TestCase):
    """SSE 事件编码测试"""

    def test_sse_encode_dict(self) -> None:
        """dict 数据编码为 JSON"""
        from dochris.api.sse import sse_encode

        result = sse_encode("test", {"key": "value"})
        self.assertIn("event: test\n", result)
        self.assertIn('data: {"key": "value"}\n', result)

    def test_sse_encode_string(self) -> None:
        """string 数据原样输出"""
        from dochris.api.sse import sse_encode

        result = sse_encode("answer_delta", "hello world")
        self.assertIn("event: answer_delta\n", result)
        self.assertIn("data: hello world\n", result)

    def test_sse_encode_with_id(self) -> None:
        """带 event_id 的编码"""
        from dochris.api.sse import sse_encode

        result = sse_encode("done", {"status": "ok"}, event_id="evt-123")
        self.assertIn("id: evt-123\n", result)

    def test_meta_event_format(self) -> None:
        """meta 事件格式正确"""
        from dochris.api.sse import sse_meta_event

        result = sse_meta_event(
            query="test", mode="combined", search_sources=["wiki"], time_seconds=1.23
        )
        self.assertIn("event: meta\n", result)
        self.assertIn('"query": "test"', result)
        self.assertIn('"v": 1', result)

    def test_done_event_with_trace_id(self) -> None:
        """done 事件包含 trace_id"""
        from dochris.api.sse import sse_done_event

        result = sse_done_event(time_seconds=2.5, trace_id="abc123")
        self.assertIn("event: done\n", result)
        self.assertIn('"trace_id": "abc123"', result)

    def test_error_event(self) -> None:
        """error 事件格式"""
        from dochris.api.sse import sse_error_event

        result = sse_error_event("Something went wrong")
        self.assertIn("event: error\n", result)
        self.assertIn('"message": "Something went wrong"', result)

    def test_ping_event(self) -> None:
        """ping 心跳事件"""
        from dochris.api.sse import sse_ping_event

        result = sse_ping_event()
        self.assertIn("event: ping\n", result)

    def test_event_name_enum(self) -> None:
        """事件名枚举值正确"""
        from dochris.api.sse import QueryStreamEventName

        self.assertEqual(QueryStreamEventName.META, "meta")
        self.assertEqual(QueryStreamEventName.ANSWER_DELTA, "answer_delta")
        self.assertEqual(QueryStreamEventName.DONE, "done")
        self.assertEqual(QueryStreamEventName.ERROR, "error")
        self.assertEqual(QueryStreamEventName.PING, "ping")


# ============================================================
# ObservabilityManager 测试
# ============================================================


class TestObservabilityManager(TestCase):
    """ObservabilityManager 门面测试"""

    def test_disabled_is_noop(self) -> None:
        """disabled 时 record 方法不报错"""
        from dochris.observability import ObservabilityManager

        obs = ObservabilityManager(enabled=False)
        self.assertFalse(obs.enabled)

        # 这些都不应报错
        obs.record_llm_usage(
            LLMUsage(provider="test", model="m1", operation="gen", prompt_tokens=100)
        )
        obs.record_retrieval(query="test", candidate_count=5, latency_ms=100)

    def test_span_always_works(self) -> None:
        """span 即使 disabled 也能用"""
        from dochris.observability import ObservabilityManager

        obs = ObservabilityManager(enabled=False)
        with obs.span("test") as ctx:
            self.assertIsInstance(ctx, SpanContext)


# ============================================================
# Metrics 注册测试
# ============================================================


class TestMetricsRegistration(TestCase):
    """Prometheus 指标注册测试"""

    def test_generate_metrics_returns_string(self) -> None:
        """generate_metrics 返回字符串"""
        # 即使未注册也应返回空字符串或有效输出
        result = generate_metrics()
        self.assertIsInstance(result, str)

    def test_record_functions_dont_crash_without_prometheus(self) -> None:
        """指标记录函数在无 prometheus 时不崩溃"""
        from dochris.observability.metrics import (
            record_cache,
            record_query,
            record_rerank,
            record_retrieval,
        )

        # 这些不应抛异常
        record_query(mode="combined")
        record_retrieval(retriever="chromadb")
        record_rerank(provider="bge")
        record_cache(result="hit")
