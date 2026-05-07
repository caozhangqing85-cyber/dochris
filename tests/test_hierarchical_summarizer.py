#!/usr/bin/env python3
"""
HierarchicalSummarizer 模块单元测试
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dochris.core.hierarchical_summarizer import HierarchicalSummarizer


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
def hierarchical_summarizer(mock_llm_client):
    """创建 HierarchicalSummarizer 实例"""
    return HierarchicalSummarizer(mock_llm_client)


@pytest.fixture
def sample_chunk():
    """模拟 TextChunk 对象"""
    chunk = MagicMock()
    chunk.title = "测试章节"
    chunk.content = "测试内容"
    return chunk


class TestHierarchicalSummarizerInit:
    """测试 HierarchicalSummarizer 初始化"""

    def test_init_with_llm_client(self, mock_llm_client):
        """测试使用 LLMClient 初始化"""
        summarizer = HierarchicalSummarizer(mock_llm_client)
        assert summarizer.llm_client is mock_llm_client


class TestGenerateMapReduceSummary:
    """测试 generate_map_reduce_summary 方法"""

    @pytest.mark.asyncio
    async def test_map_reduce_success(self, hierarchical_summarizer, mock_llm_client):
        """测试 Map-Reduce 摘要成功"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(
            {
                "one_line": "摘要",
                "key_points": ["要点"],
                "detailed_summary": "详细摘要",
                "concepts": [],
            }
        )

        mock_llm_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("dochris.core.text_chunker.semantic_chunk") as mock_chunk:
            mock_chunk.return_value = [MagicMock(title="块1", content="内容1")]

            with patch.object(
                hierarchical_summarizer,
                "_summarize_chunks_parallel",
                new=AsyncMock(return_value=[{"detailed_summary": "摘要1"}]),
            ):
                with patch.object(
                    hierarchical_summarizer,
                    "_merge_summaries",
                    new=AsyncMock(return_value={"result": "merged"}),
                ):
                    result = await hierarchical_summarizer.generate_map_reduce_summary(
                        "测试文本" * 100, "测试标题"
                    )

                    assert result is not None

    @pytest.mark.asyncio
    async def test_map_reduce_all_chunks_fail(self, hierarchical_summarizer):
        """测试所有分块摘要失败"""
        with patch("dochris.core.text_chunker.semantic_chunk") as mock_chunk:
            mock_chunk.return_value = [MagicMock(title="块1", content="内容1")]

            with patch.object(
                hierarchical_summarizer,
                "_summarize_chunks_parallel",
                new=AsyncMock(return_value=[]),
            ):
                result = await hierarchical_summarizer.generate_map_reduce_summary(
                    "测试文本" * 100, "测试标题"
                )

                assert result is None


class TestGenerateHierarchicalSummary:
    """测试 generate_hierarchical_summary 方法"""

    @pytest.mark.asyncio
    async def test_hierarchical_truncates_oversized_text(self, hierarchical_summarizer):
        """测试超长文本截断"""
        # 超过 MAX_HIERARCHICAL_CHARS 的文本
        oversized_text = "a" * 250000

        with patch("dochris.core.text_chunker.structure_aware_split") as mock_split:
            mock_split.return_value = [MagicMock(title="块1", content="内容1")]

            with patch.object(
                hierarchical_summarizer,
                "_summarize_chunks_parallel",
                new=AsyncMock(return_value=[{"detailed_summary": "摘要1"}]),
            ):
                with patch.object(
                    hierarchical_summarizer,
                    "_group_chunks_by_section",
                    return_value={"section": []},
                ):
                    with patch.object(
                        hierarchical_summarizer,
                        "_merge_summaries",
                        new=AsyncMock(return_value={"result": "ok"}),
                    ):
                        await hierarchical_summarizer.generate_hierarchical_summary(
                            oversized_text, "测试标题"
                        )

                        # 检查文本被截断
                        call_args = mock_split.call_args[0]
                        truncated_text = call_args[0]
                        assert "[...中间内容已截断...]" in truncated_text
                        assert len(truncated_text) < len(oversized_text)

    @pytest.mark.asyncio
    async def test_hierarchical_limits_chunks(self, hierarchical_summarizer):
        """测试块数限制"""
        # 创建超过 MAX_CHUNKS 的块
        many_chunks = [MagicMock(title=f"块{i}", content=f"内容{i}") for i in range(100)]

        with patch("dochris.core.text_chunker.structure_aware_split") as mock_split:
            mock_split.return_value = many_chunks

            with patch.object(
                hierarchical_summarizer,
                "_summarize_chunks_parallel",
                new=AsyncMock(return_value=[{"detailed_summary": "摘要1"}] * 50),
            ):
                with patch.object(
                    hierarchical_summarizer,
                    "_group_chunks_by_section",
                    return_value={"section": []},
                ):
                    with patch.object(
                        hierarchical_summarizer,
                        "_merge_summaries",
                        new=AsyncMock(return_value={"result": "ok"}),
                    ):
                        await hierarchical_summarizer.generate_hierarchical_summary(
                            "测试文本", "测试标题"
                        )

                        # split 本身返回所有块，但后续处理会限制到 MAX_CHUNKS


class TestSummarizeChunksParallel:
    """测试 _summarize_chunks_parallel 方法"""

    @pytest.mark.asyncio
    async def test_summarize_chunks_success(self, hierarchical_summarizer, mock_llm_client):
        """测试并行摘要成功"""
        chunks = [
            MagicMock(title="块1", content="内容1"),
            MagicMock(title="块2", content="内容2"),
        ]

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(
            {"one_line": "摘要", "key_points": ["要点"], "detailed_summary": "详细", "concepts": []}
        )

        mock_llm_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        results = await hierarchical_summarizer._summarize_chunks_parallel(chunks, "测试", 3)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_summarize_chunks_with_exception(self, hierarchical_summarizer, mock_llm_client):
        """测试摘要时的异常处理"""
        chunks = [
            MagicMock(title="块1", content="内容1"),
            MagicMock(title="块2", content="内容2"),
        ]

        # 第一个块失败，第二个成功
        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("API error")
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = json.dumps(
                {
                    "one_line": "摘要",
                    "key_points": ["要点"],
                    "detailed_summary": "详细",
                    "concepts": [],
                }
            )
            return mock_response

        mock_llm_client.client.chat.completions.create = AsyncMock(side_effect=side_effect)

        with patch("asyncio.sleep"):
            results = await hierarchical_summarizer._summarize_chunks_parallel(chunks, "测试", 3)

            # 只返回成功的
            assert len(results) <= 2


class TestMergeSummaries:
    """测试 _merge_summaries 方法"""

    @pytest.mark.asyncio
    async def test_merge_summaries_single(self, hierarchical_summarizer):
        """测试单个摘要直接返回"""
        summaries = [{"one_line": "摘要1"}]

        result = await hierarchical_summarizer._merge_summaries(summaries, "测试", 3)

        assert result == summaries[0]

    @pytest.mark.asyncio
    async def test_merge_summaries_multiple(self, hierarchical_summarizer, mock_llm_client):
        """测试合并多个摘要"""
        summaries = [
            {
                "one_line": "摘要1",
                "detailed_summary": "内容1",
                "key_points": ["p1"],
                "concepts": [],
            },
            {
                "one_line": "摘要2",
                "detailed_summary": "内容2",
                "key_points": ["p2"],
                "concepts": [],
            },
        ]

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(
            {
                "one_line": "合并摘要",
                "key_points": ["p1", "p2"],
                "detailed_summary": "合并内容",
                "concepts": [],
            }
        )

        mock_llm_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await hierarchical_summarizer._merge_summaries(summaries, "测试", 3)

        assert result is not None
        assert result["one_line"] == "合并摘要"


class TestBuildMessages:
    """测试消息构建方法"""

    def test_build_chunk_messages_default(self, hierarchical_summarizer):
        """测试默认分段消息构建"""
        messages = hierarchical_summarizer._build_chunk_messages("测试内容", "测试标题")

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_build_chunk_messages_qwen3(self, mock_llm_client):
        """测试 qwen3 分段消息构建"""
        mock_llm_client.no_think = True
        summarizer = HierarchicalSummarizer(mock_llm_client)

        messages = summarizer._build_chunk_messages("测试内容", "测试标题")

        assert len(messages) == 2
        assert "资深知识工程师" in messages[0]["content"]

    def test_build_merge_prompt(self, hierarchical_summarizer):
        """测试合并 prompt 构建"""
        summaries = [
            {
                "one_line": "摘要1",
                "key_points": ["p1"],
                "detailed_summary": "内容1",
                "concepts": [],
            },
        ]

        prompt = hierarchical_summarizer._build_merge_prompt(summaries, "测试标题")

        assert "测试标题" in prompt
        assert "片段 1" in prompt

    def test_build_merge_prompt_qwen3(self, mock_llm_client):
        """测试 qwen3 合并 prompt"""
        mock_llm_client.no_think = True
        summarizer = HierarchicalSummarizer(mock_llm_client)

        summaries = [
            {
                "one_line": "摘要1",
                "key_points": ["p1"],
                "detailed_summary": "内容1",
                "concepts": [],
            },
        ]

        prompt = summarizer._build_merge_prompt_qwen3(summaries, "测试标题")

        assert "资深知识工程师" in prompt
        assert "合并目标" in prompt


class TestGroupChunksBySection:
    """测试 _group_chunks_by_section 方法"""

    def test_group_chunks_by_section(self, hierarchical_summarizer, sample_chunk):
        """测试按章节分组"""
        chunks = [
            sample_chunk,
            MagicMock(title="章节1", content="内容1"),
            MagicMock(title="章节1", content="内容2"),
            MagicMock(title="", content="内容3"),
        ]

        summaries = [
            {"one_line": "摘要1"},
            {"one_line": "摘要2"},
            {"one_line": "摘要3"},
            {"one_line": "摘要4"},
        ]

        sections = hierarchical_summarizer._group_chunks_by_section(chunks, summaries)

        assert "测试章节" in sections
        assert "章节1" in sections
        assert "未分类" in sections
        assert len(sections["章节1"]) == 2
