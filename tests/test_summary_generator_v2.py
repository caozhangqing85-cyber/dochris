"""测试 core/summary_generator.py 模块"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSummaryGeneratorBuildMessages:
    """测试消息构建逻辑"""

    def _make_llm_client(self, no_think=False):
        client = MagicMock()
        client.no_think = no_think
        return client

    def test_build_messages_default(self):
        """非 qwen3 模型使用默认模板"""
        from dochris.core.summary_generator import SummaryGenerator

        gen = SummaryGenerator(self._make_llm_client(no_think=False))
        msgs = gen._build_messages("some text", "test title")

        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"
        assert "test title" in msgs[1]["content"]
        assert "some text" in msgs[1]["content"]

    def test_build_messages_qwen3(self):
        """qwen3 模型使用专用模板"""
        from dochris.core.summary_generator import SummaryGenerator

        gen = SummaryGenerator(self._make_llm_client(no_think=True))
        msgs = gen._build_messages_qwen3("some text", "qwen title")

        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert "知识工程师" in msgs[0]["content"]
        assert "qwen title" in msgs[1]["content"]

    def test_build_messages_selects_qwen3_when_no_think(self):
        """no_think=True 时自动选择 qwen3 模板"""
        from dochris.core.summary_generator import SummaryGenerator

        gen = SummaryGenerator(self._make_llm_client(no_think=True))
        msgs = gen._build_messages("text", "title")

        assert "知识工程师" in msgs[0]["content"]


class TestSummaryGeneratorGenerate:
    """测试 generate_summary 函数"""

    def _make_llm_client(self):
        client = MagicMock()
        client.model = "test-model"
        client.max_tokens = 4000
        client.temperature = 0.1
        client.no_think = False

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "one_line": "test",
            "key_points": ["a"],
            "detailed_summary": "summary",
            "concepts": [{"name": "c1", "explanation": "exp"}],
        })

        client.client = MagicMock()
        client.client.chat.completions.create = AsyncMock(return_value=mock_response)
        client._rate_limit = AsyncMock()
        client._apply_no_think = lambda msgs: msgs
        client._extract_json_from_text = MagicMock(return_value=None)
        return client

    @pytest.mark.asyncio
    async def test_generate_summary_success(self):
        """正常生成摘要"""
        from dochris.core.summary_generator import SummaryGenerator

        gen = SummaryGenerator(self._make_llm_client())
        result = await gen.generate_summary("text content", "title")

        assert result is not None
        assert result["one_line"] == "test"
        assert len(result["key_points"]) == 1

    @pytest.mark.asyncio
    async def test_generate_summary_json_decode_fallback(self):
        """JSON 解析失败时使用 json_repair"""
        client = self._make_llm_client()
        # 返回非法 JSON
        client.client.chat.completions.create = AsyncMock(
            return_value=MagicMock(
                choices=[MagicMock(
                    message=MagicMock(content='{"one_line": "ok", invalid json}')
                )]
            )
        )
        # json_repair 能修复
        with patch("json_repair.loads", return_value={"one_line": "repaired"}):
            from dochris.core.summary_generator import SummaryGenerator

            gen = SummaryGenerator(client)
            result = await gen.generate_summary("text", "title", max_retries=1)
            assert result is not None
            assert result["one_line"] == "repaired"

    @pytest.mark.asyncio
    async def test_generate_summary_all_fail_returns_none(self):
        """所有重试失败返回 None"""
        client = self._make_llm_client()
        client.client.chat.completions.create = AsyncMock(
            side_effect=Exception("API error")
        )

        from dochris.core.summary_generator import SummaryGenerator

        gen = SummaryGenerator(client)
        result = await gen.generate_summary("text", "title", max_retries=1)
        assert result is None


class TestSummaryGeneratorSmart:
    """测试 generate_summary_smart 策略选择"""

    def _make_llm_client(self):
        client = MagicMock()
        client.model = "test"
        client.max_tokens = 4000
        client.temperature = 0.1
        client.no_think = False
        return client

    @pytest.mark.asyncio
    async def test_direct_strategy_short_text(self):
        """短文本使用 direct 策略"""
        from dochris.core.summary_generator import SummaryGenerator

        gen = SummaryGenerator(self._make_llm_client())

        with patch.object(gen, "generate_summary", new_callable=AsyncMock, return_value={"one_line": "ok"}) as mock_direct:
            result = await gen.generate_summary_smart("short text", "title", direct_limit=10000)
            mock_direct.assert_awaited_once()
            assert result is not None

    @pytest.mark.asyncio
    async def test_map_reduce_strategy_medium_text(self):
        """中等文本使用 map_reduce 策略"""
        from dochris.core.summary_generator import SummaryGenerator

        gen = SummaryGenerator(self._make_llm_client())
        medium_text = "x" * 20000  # 超过 direct_limit=10000 但小于 30000

        mock_mr = AsyncMock(return_value={"one_line": "mr"})
        with patch(
            "dochris.core.hierarchical_summarizer.HierarchicalSummarizer.generate_map_reduce_summary",
            mock_mr,
        ):
            result = await gen.generate_summary_smart(medium_text, "title", direct_limit=10000)
            assert result is not None

    @pytest.mark.asyncio
    async def test_hierarchical_strategy_long_text(self):
        """长文本使用 hierarchical 策略"""
        from dochris.core.summary_generator import SummaryGenerator

        gen = SummaryGenerator(self._make_llm_client())
        long_text = "x" * 50000  # 超过 30000

        mock_hier = AsyncMock(return_value={"one_line": "hier"})
        with patch(
            "dochris.core.hierarchical_summarizer.HierarchicalSummarizer.generate_hierarchical_summary",
            mock_hier,
        ):
            result = await gen.generate_summary_smart(long_text, "title", direct_limit=10000)
            assert result is not None
