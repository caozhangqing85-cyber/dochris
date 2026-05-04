"""测试 SummaryGenerator"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dochris.core.retry_manager import RetryManager
from dochris.core.summary_generator import SummaryGenerator


@pytest.fixture
def mock_llm_client():
    """创建模拟的 LLMClient"""
    client = MagicMock()
    client.model = "test-model"
    client.max_tokens = 4000
    client.temperature = 0.7
    client.no_think = False
    client._rate_limit = AsyncMock()
    client._apply_no_think = MagicMock(side_effect=lambda msgs: msgs)
    client._extract_json_from_text = MagicMock(return_value=None)
    client.client = MagicMock()
    return client


@pytest.fixture
def generator(mock_llm_client):
    return SummaryGenerator(mock_llm_client)


def _make_response(content: str):
    """构造 LLM 响应对象"""
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    return resp


# ---- _build_messages ----


class TestBuildMessages:
    def test_default_messages_structure(self, generator):
        msgs = generator._build_messages("some text", "title")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"
        assert "some text" in msgs[1]["content"]
        assert "title" in msgs[1]["content"]

    def test_qwen3_messages_when_no_think(self, generator, mock_llm_client):
        mock_llm_client.no_think = True
        msgs = generator._build_messages("text", "t")
        assert "资深知识工程师" in msgs[0]["content"]

    def test_default_messages_no_qwen3(self, generator, mock_llm_client):
        mock_llm_client.no_think = False
        msgs = generator._build_messages("text", "t")
        assert "资深知识工程师" not in msgs[0]["content"]
        assert "知识库编译器" in msgs[0]["content"]


class TestBuildMessagesQwen3:
    def test_output_contains_system_and_user(self, generator):
        msgs = generator._build_messages_qwen3("hello", "mytitle")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"
        assert "mytitle" in msgs[1]["content"]

    def test_system_prompt_has_json_spec(self, generator):
        msgs = generator._build_messages_qwen3("x", "y")
        assert "one_line" in msgs[0]["content"]
        assert "concepts" in msgs[0]["content"]


# ---- generate_summary ----


class TestGenerateSummary:
    @pytest.mark.asyncio
    async def test_successful_json_response(self, generator, mock_llm_client):
        result_data = {
            "one_line": "test summary",
            "key_points": ["a", "b"],
            "detailed_summary": "details",
            "concepts": [{"name": "c1"}],
        }
        resp = _make_response(json.dumps(result_data))
        mock_llm_client.client.chat.completions.create = AsyncMock(return_value=resp)

        result = await generator.generate_summary("text", "title", max_retries=1)
        assert result is not None
        assert result["one_line"] == "test summary"

    @pytest.mark.asyncio
    async def test_invalid_json_with_json_repair(self, generator, mock_llm_client):
        resp = _make_response('{"one_line": "ok", invalid}')
        mock_llm_client.client.chat.completions.create = AsyncMock(return_value=resp)

        with patch("dochris.core.summary_generator.json_repair", create=True) as jr:
            jr.loads = MagicMock(return_value={"one_line": "repaired"})
            # json_repair needs to be importable
            with patch.dict("sys.modules", {"json_repair": jr}):
                import sys

                sys.modules["json_repair"] = jr
                result = await generator.generate_summary("text", "title", max_retries=1)

        assert result is not None
        assert result["one_line"] == "repaired"

    @pytest.mark.asyncio
    async def test_empty_response_returns_empty_string(self, generator, mock_llm_client):
        """空字符串响应: json_repair.loads('') 返回空字符串"""
        resp = _make_response("")
        mock_llm_client.client.chat.completions.create = AsyncMock(return_value=resp)

        result = await generator.generate_summary("text", "title", max_retries=1)
        # json_repair.loads('') 返回 ''
        assert result == ""

    @pytest.mark.asyncio
    async def test_api_error_returns_none(self, generator, mock_llm_client):
        mock_llm_client.client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("API error")
        )

        result = await generator.generate_summary("text", "title", max_retries=1)
        assert result is None


# ---- generate_summary_smart ----


class TestGenerateSummarySmart:
    @pytest.mark.asyncio
    async def test_short_text_uses_direct(self, generator, mock_llm_client):
        """短文本应使用直接策略"""
        result_data = {
            "one_line": "short",
            "key_points": [],
            "detailed_summary": "",
            "concepts": [],
        }
        resp = _make_response(json.dumps(result_data))
        mock_llm_client.client.chat.completions.create = AsyncMock(return_value=resp)

        with patch("dochris.core.text_chunker.should_use_hierarchical", return_value="direct"):
            result = await generator.generate_summary_smart("short text", "title")

        assert result is not None
        assert result["one_line"] == "short"

    @pytest.mark.asyncio
    async def test_map_reduce_strategy(self, generator, mock_llm_client):
        """中等长度文本使用 map_reduce"""
        with patch("dochris.core.text_chunker.should_use_hierarchical", return_value="map_reduce"):
            mock_summarizer = MagicMock()
            mock_summarizer.generate_map_reduce_summary = AsyncMock(
                return_value={
                    "one_line": "mr",
                    "key_points": [],
                    "detailed_summary": "",
                    "concepts": [],
                }
            )
            with patch(
                "dochris.core.hierarchical_summarizer.HierarchicalSummarizer",
                return_value=mock_summarizer,
            ):
                result = await generator.generate_summary_smart("medium text", "title")

        assert result is not None
        assert result["one_line"] == "mr"

    @pytest.mark.asyncio
    async def test_hierarchical_strategy(self, generator, mock_llm_client):
        """长文本使用 hierarchical"""
        with patch(
            "dochris.core.text_chunker.should_use_hierarchical",
            return_value="hierarchical",
        ):
            mock_summarizer = MagicMock()
            mock_summarizer.generate_hierarchical_summary = AsyncMock(
                return_value={
                    "one_line": "hi",
                    "key_points": [],
                    "detailed_summary": "",
                    "concepts": [],
                }
            )
            with patch(
                "dochris.core.hierarchical_summarizer.HierarchicalSummarizer",
                return_value=mock_summarizer,
            ):
                result = await generator.generate_summary_smart("long text", "title")

        assert result is not None
        assert result["one_line"] == "hi"


# ---- RetryManager integration ----


class TestRetryManagerIntegration:
    @pytest.mark.asyncio
    async def test_content_filter_returns_none(self, generator, mock_llm_client):
        """content filter 触发时应返回 None"""
        mock_llm_client.client.chat.completions.create = AsyncMock(
            side_effect=Exception("ContentFilter triggered")
        )

        result = await generator.generate_summary("text", "title", max_retries=2)
        assert result is None


# ---- RetryManager ----


class TestRetryManager:
    def test_get_error_type_429(self):
        assert RetryManager.get_error_type(Exception("429 rate limit")) == "rate_limit_429"

    def test_get_error_type_timeout(self):
        assert RetryManager.get_error_type(Exception("timeout occurred")) == "timeout"

    def test_get_error_type_other(self):
        assert RetryManager.get_error_type(Exception("random error")) == "other"

    def test_should_retry_within_limit(self):
        err = Exception("429")
        assert RetryManager.should_retry(err, 0) is True

    def test_should_retry_exceeds_limit(self):
        err = Exception("429")
        assert RetryManager.should_retry(err, 10) is False

    def test_get_retry_delay_exponential(self):
        err = Exception("429")
        d0 = RetryManager.get_retry_delay(0, err)
        d1 = RetryManager.get_retry_delay(1, err)
        assert d1 > d0

    def test_get_retry_delay_without_error(self):
        d = RetryManager.get_retry_delay(0)
        assert d > 0

    @pytest.mark.asyncio
    async def test_retry_success_first_try(self):
        async def ok_func():
            return "success"

        result = await RetryManager.retry(ok_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_success_after_failure(self):
        calls = 0

        async def flaky():
            nonlocal calls
            calls += 1
            if calls < 3:
                raise ConnectionError("fail")
            return "recovered"

        with patch("dochris.core.retry_manager.asyncio.sleep", new_callable=AsyncMock):
            result = await RetryManager.retry(flaky, max_attempts=5)
        assert result == "recovered"

    @pytest.mark.asyncio
    async def test_retry_sync_function(self):
        def sync_ok():
            return "sync_result"

        result = await RetryManager.retry(sync_ok)
        assert result == "sync_result"

    @pytest.mark.asyncio
    async def test_retry_all_attempts_fail(self):
        async def always_fail():
            raise RuntimeError("always fails")

        with patch("dochris.core.retry_manager.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="always fails"):
                await RetryManager.retry(always_fail, max_attempts=1)

    @pytest.mark.asyncio
    async def test_llm_retry_with_filter_content_filter(self):
        async def trigger_filter():
            raise Exception("content filter detected")

        result = await RetryManager.llm_retry_with_filter(trigger_filter, max_retries=2)
        assert result is None

    @pytest.mark.asyncio
    async def test_llm_retry_with_filter_success(self):
        async def ok():
            return {"data": "ok"}

        result = await RetryManager.llm_retry_with_filter(ok)
        assert result == {"data": "ok"}

    @pytest.mark.asyncio
    async def test_llm_retry_with_filter_429_retry(self):
        calls = 0

        async def rate_limited():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise Exception("429 rate limit")
            return "ok"

        with patch("dochris.core.retry_manager.asyncio.sleep", new_callable=AsyncMock):
            result = await RetryManager.llm_retry_with_filter(rate_limited, max_retries=3)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_llm_retry_with_filter_connection_error(self):
        calls = 0

        async def conn_err():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise Exception("connection timeout")
            return "ok"

        with patch("dochris.core.retry_manager.asyncio.sleep", new_callable=AsyncMock):
            result = await RetryManager.llm_retry_with_filter(conn_err, max_retries=3)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_llm_retry_with_filter_exhausted(self):
        async def always_fail():
            raise RuntimeError("persistent error")

        with patch("dochris.core.retry_manager.asyncio.sleep", new_callable=AsyncMock):
            result = await RetryManager.llm_retry_with_filter(always_fail, max_retries=2)
        assert result is None
