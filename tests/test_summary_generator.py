#!/usr/bin/env python3
"""
SummaryGenerator 模块单元测试
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dochris.core.summary_generator import SummaryGenerator


@pytest.fixture
def mock_llm_client():
    """模拟 LLMClient"""
    client = MagicMock()
    client.client = MagicMock()
    client.client.chat = MagicMock()
    client.client.chat.completions = MagicMock()
    client.model = "test-model"
    client.max_tokens = 4000
    client.temperature = 0.1
    client.no_think = False
    client._rate_limit = AsyncMock()
    client._apply_no_think = lambda x: x
    client._extract_json_from_text = MagicMock(return_value=None)
    return client


@pytest.fixture
def summary_generator(mock_llm_client):
    """创建 SummaryGenerator 实例"""
    return SummaryGenerator(mock_llm_client)


class TestSummaryGeneratorInit:
    """测试 SummaryGenerator 初始化"""

    def test_init_with_llm_client(self, mock_llm_client):
        """测试使用 LLMClient 初始化"""
        generator = SummaryGenerator(mock_llm_client)
        assert generator.llm_client is mock_llm_client


class TestGenerateSummary:
    """测试 generate_summary 方法"""

    @pytest.mark.asyncio
    async def test_generate_summary_success(self, summary_generator, mock_llm_client):
        """测试成功生成摘要"""
        # 模拟 LLM 响应
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "one_line": "测试摘要",
            "key_points": ["要点1", "要点2"],
            "detailed_summary": "详细摘要内容",
            "concepts": [{"name": "概念1", "explanation": "解释"}]
        })

        mock_llm_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await summary_generator.generate_summary("测试内容", "测试标题")

        assert result is not None
        assert result["one_line"] == "测试摘要"
        assert len(result["key_points"]) == 2
        assert result["detailed_summary"] == "详细摘要内容"
        assert len(result["concepts"]) == 1

    @pytest.mark.asyncio
    async def test_generate_summary_with_invalid_json(self, summary_generator, mock_llm_client):
        """测试 JSON 解析失败时的错误处理"""
        pytest.skip("json_repair integration test - requires json_repair package")

    @pytest.mark.asyncio
    async def test_generate_summary_429_retry(self, summary_generator, mock_llm_client):
        """测试 429 错误重试"""
        # 第一次调用返回 429 错误，第二次成功
        mock_response_429 = MagicMock()
        mock_response_429.choices = [MagicMock()]
        mock_response_429.choices[0].message.content = "content"

        mock_response_success = MagicMock()
        mock_response_success.choices = [MagicMock()]
        mock_response_success.choices[0].message.content = json.dumps({
            "one_line": "测试摘要",
            "key_points": ["要点1"],
            "detailed_summary": "详细",
            "concepts": []
        })

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("429 rate limit exceeded")
            return mock_response_success

        mock_llm_client.client.chat.completions.create = AsyncMock(side_effect=side_effect)

        with patch("asyncio.sleep"):  # 跳过 sleep
            result = await summary_generator.generate_summary("测试内容", "测试标题", max_retries=3)

        assert result is not None
        assert call_count == 2  # 第一次失败，第二次成功

    @pytest.mark.asyncio
    async def test_generate_summary_content_filter(self, summary_generator, mock_llm_client):
        """测试内容过滤直接返回 None"""
        async def raise_content_filter(*args, **kwargs):
            raise Exception("contentFilter triggered")

        mock_llm_client.client.chat.completions.create = AsyncMock(side_effect=raise_content_filter)

        result = await summary_generator.generate_summary("测试内容", "测试标题", max_retries=3)

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_summary_max_retries_exceeded(self, summary_generator, mock_llm_client):
        """测试超过最大重试次数"""
        mock_llm_client.client.chat.completions.create = AsyncMock(
            side_effect=Exception("API error")
        )

        with patch("asyncio.sleep"):  # 跳过 sleep
            result = await summary_generator.generate_summary(
                "测试内容", "测试标题", max_retries=2
            )

        assert result is None


class TestBuildMessages:
    """测试 _build_messages 方法"""

    def test_build_messages_default(self, summary_generator):
        """测试默认消息构建"""
        messages = summary_generator._build_messages("测试内容", "测试标题")

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "测试标题" in messages[1]["content"]
        assert "测试内容" in messages[1]["content"]

    def test_build_messages_qwen3(self, mock_llm_client):
        """测试 qwen3 模型的消息构建"""
        mock_llm_client.no_think = True
        generator = SummaryGenerator(mock_llm_client)

        messages = generator._build_messages("测试内容", "测试标题")

        assert len(messages) == 2
        assert "资深知识工程师" in messages[0]["content"]


class TestGenerateSummarySmart:
    """测试 generate_summary_smart 方法"""

    @pytest.mark.asyncio
    async def test_short_text_direct_strategy(self, summary_generator):
        """测试短文本使用直接策略"""
        short_text = "a" * 5000  # 小于 direct_limit

        with patch.object(
            summary_generator, "generate_summary", new=AsyncMock(return_value={"result": "direct"})
        ) as mock_generate:
            result = await summary_generator.generate_summary_smart(short_text, "测试")

            assert result is not None
            mock_generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_map_reduce_strategy(self, summary_generator):
        """测试 Map-Reduce 策略"""
        medium_text = "a" * 15000  # direct_limit ~ direct_limit*3

        with patch("dochris.core.text_chunker.should_use_hierarchical") as mock_strategy:
            mock_strategy.return_value = "map_reduce"

            with patch("dochris.core.hierarchical_summarizer.HierarchicalSummarizer") as mock_summarizer:
                mock_instance = MagicMock()
                mock_instance.generate_map_reduce_summary = AsyncMock(
                    return_value={"result": "map_reduce"}
                )
                mock_summarizer.return_value = mock_instance

                result = await summary_generator.generate_summary_smart(medium_text, "测试")

                assert result is not None
                mock_instance.generate_map_reduce_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_hierarchical_strategy(self, summary_generator):
        """测试分层策略"""
        long_text = "a" * 35000  # 大于 direct_limit*3

        with patch("dochris.core.text_chunker.should_use_hierarchical") as mock_strategy:
            mock_strategy.return_value = "hierarchical"

            with patch("dochris.core.hierarchical_summarizer.HierarchicalSummarizer") as mock_summarizer:
                mock_instance = MagicMock()
                mock_instance.generate_hierarchical_summary = AsyncMock(
                    return_value={"result": "hierarchical"}
                )
                mock_summarizer.return_value = mock_instance

                result = await summary_generator.generate_summary_smart(long_text, "测试")

                assert result is not None
                mock_instance.generate_hierarchical_summary.assert_called_once()
