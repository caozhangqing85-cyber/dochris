#!/usr/bin/env python3
"""
层次化摘要器增强测试 — 边界条件和 Map-Reduce 边缘场景
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dochris.core.hierarchical_summarizer import (
    MAX_HIERARCHICAL_CHARS,
    HierarchicalSummarizer,
)


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
def summarizer(mock_llm_client):
    """创建 HierarchicalSummarizer 实例"""
    return HierarchicalSummarizer(mock_llm_client)


def _make_mock_response(data: dict) -> MagicMock:
    """创建模拟 LLM 响应"""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = json.dumps(data, ensure_ascii=False)
    return response


SAMPLE_SUMMARY = {
    "one_line": "测试摘要",
    "key_points": ["要点1", "要点2"],
    "detailed_summary": "详细内容" * 20,
    "concepts": [{"name": "概念1", "explanation": "解释"}],
}


class TestMapReduceEdgeCases:
    """Map-Reduce 边界条件测试"""

    @pytest.mark.asyncio
    async def test_empty_text(self, summarizer):
        """空文本分块后应返回 None（无有效块）"""
        with patch.object(
            summarizer,
            "_summarize_chunks_parallel",
            new=AsyncMock(return_value=[]),
        ):
            result = await summarizer.generate_map_reduce_summary("", "空文档")
            assert result is None

    @pytest.mark.asyncio
    async def test_single_chunk(self, summarizer, mock_llm_client):
        """单个分块直接摘要"""
        mock_llm_client.client.chat.completions.create = AsyncMock(
            return_value=_make_mock_response(SAMPLE_SUMMARY)
        )

        with patch("dochris.core.text_chunker.semantic_chunk") as mock_chunk:
            mock_chunk.return_value = [MagicMock(title="唯一块", content="内容" * 50)]

            with patch.object(
                summarizer,
                "_summarize_chunks_parallel",
                new=AsyncMock(return_value=[SAMPLE_SUMMARY]),
            ):
                with patch.object(
                    summarizer, "_merge_summaries", new=AsyncMock(return_value=SAMPLE_SUMMARY)
                ):
                    result = await summarizer.generate_map_reduce_summary(
                        "测试文本" * 100, "单块文档"
                    )
                    assert result is not None

    @pytest.mark.asyncio
    async def test_all_chunks_fail(self, summarizer):
        """所有分块摘要失败"""
        with patch("dochris.core.text_chunker.semantic_chunk") as mock_chunk:
            mock_chunk.return_value = [MagicMock(title="块1", content="内容")]

            with patch.object(
                summarizer,
                "_summarize_chunks_parallel",
                new=AsyncMock(return_value=[]),
            ):
                result = await summarizer.generate_map_reduce_summary(
                    "测试文本" * 100, "全失败文档"
                )
                assert result is None

    @pytest.mark.asyncio
    async def test_unicode_content(self, summarizer, mock_llm_client):
        """Unicode 内容（中文、emoji）"""
        unicode_summary = {
            "one_line": "这是一份关于🎉的文档",
            "key_points": ["要点🌟", "要点📚"],
            "detailed_summary": "详细内容包含中文和 emoji 🎊",
            "concepts": [],
        }
        mock_llm_client.client.chat.completions.create = AsyncMock(
            return_value=_make_mock_response(unicode_summary)
        )

        with patch.object(
            summarizer,
            "_summarize_chunks_parallel",
            new=AsyncMock(return_value=[unicode_summary]),
        ):
            with patch.object(
                summarizer, "_merge_summaries", new=AsyncMock(return_value=unicode_summary)
            ):
                result = await summarizer.generate_map_reduce_summary(
                    "包含🎉🎊📚的内容" * 100, "Unicode 文档"
                )
                assert result is not None
                assert "🎉" in result["one_line"]

    @pytest.mark.asyncio
    async def test_mixed_language_content(self, summarizer, mock_llm_client):
        """中英混合内容"""
        mixed_summary = {
            "one_line": "A study on machine learning 机器学习研究",
            "key_points": ["Deep Learning 深度学习", "NLP 自然语言处理"],
            "detailed_summary": "This paper discusses machine learning techniques 本文讨论机器学习技术",
            "concepts": [],
        }
        mock_llm_client.client.chat.completions.create = AsyncMock(
            return_value=_make_mock_response(mixed_summary)
        )

        with patch.object(
            summarizer,
            "_summarize_chunks_parallel",
            new=AsyncMock(return_value=[mixed_summary]),
        ):
            with patch.object(
                summarizer, "_merge_summaries", new=AsyncMock(return_value=mixed_summary)
            ):
                result = await summarizer.generate_map_reduce_summary(
                    "Machine learning 机器学习 content" * 100, "Mixed Language"
                )
                assert result is not None


class TestHierarchicalEdgeCases:
    """分层摘要边界条件"""

    @pytest.mark.asyncio
    async def test_text_at_exact_limit(self, summarizer):
        """恰好等于 MAX_HIERARCHICAL_CHARS 的文本不截断"""
        text = "a" * MAX_HIERARCHICAL_CHARS

        with patch("dochris.core.text_chunker.structure_aware_split") as mock_split:
            mock_split.return_value = [MagicMock(title="块1", content="内容")]

            with patch.object(
                summarizer,
                "_summarize_chunks_parallel",
                new=AsyncMock(return_value=[SAMPLE_SUMMARY]),
            ):
                with patch.object(
                    summarizer, "_group_chunks_by_section", return_value={"section": []}
                ):
                    with patch.object(
                        summarizer, "_merge_summaries", new=AsyncMock(return_value=SAMPLE_SUMMARY)
                    ):
                        await summarizer.generate_hierarchical_summary(text, "边界测试")

                        # 不应该截断
                        call_text = mock_split.call_args[0][0]
                        assert "[...中间内容已截断...]" not in call_text

    @pytest.mark.asyncio
    async def test_text_exceeds_limit_truncates(self, summarizer):
        """超过 MAX_HIERARCHICAL_CHARS 的文本截断"""
        text = "a" * (MAX_HIERARCHICAL_CHARS + 1000)

        with patch("dochris.core.text_chunker.structure_aware_split") as mock_split:
            mock_split.return_value = [MagicMock(title="块1", content="内容")]

            with patch.object(
                summarizer,
                "_summarize_chunks_parallel",
                new=AsyncMock(return_value=[SAMPLE_SUMMARY]),
            ):
                with patch.object(
                    summarizer, "_group_chunks_by_section", return_value={"section": []}
                ):
                    with patch.object(
                        summarizer, "_merge_summaries", new=AsyncMock(return_value=SAMPLE_SUMMARY)
                    ):
                        await summarizer.generate_hierarchical_summary(text, "超长文档")

                        call_text = mock_split.call_args[0][0]
                        assert "[...中间内容已截断...]" in call_text

    @pytest.mark.asyncio
    async def test_all_chunks_identical(self, summarizer):
        """所有块内容相同"""
        identical_chunks = [MagicMock(title=f"块{i}", content="相同内容") for i in range(3)]

        with patch("dochris.core.text_chunker.structure_aware_split") as mock_split:
            mock_split.return_value = identical_chunks

            with patch.object(
                summarizer,
                "_summarize_chunks_parallel",
                new=AsyncMock(return_value=[SAMPLE_SUMMARY] * 3),
            ):
                with patch.object(
                    summarizer,
                    "_summarize_sections_parallel",
                    new=AsyncMock(return_value=[SAMPLE_SUMMARY]),
                ):
                    with patch.object(
                        summarizer, "_merge_summaries", new=AsyncMock(return_value=SAMPLE_SUMMARY)
                    ):
                        result = await summarizer.generate_hierarchical_summary(
                            "相同内容", "重复文档"
                        )
                        assert result is not None

    @pytest.mark.asyncio
    async def test_single_section_skips_section_merge(self, summarizer):
        """只有一个章节时跳过章节合并"""
        chunks = [MagicMock(title="唯一章节", content="内容")]

        with patch("dochris.core.text_chunker.structure_aware_split") as mock_split:
            mock_split.return_value = chunks

            with patch.object(
                summarizer,
                "_summarize_chunks_parallel",
                new=AsyncMock(return_value=[SAMPLE_SUMMARY]),
            ):
                with patch.object(
                    summarizer,
                    "_group_chunks_by_section",
                    return_value={"唯一章节": [SAMPLE_SUMMARY]},
                ):
                    with patch.object(
                        summarizer, "_merge_summaries", new=AsyncMock(return_value=SAMPLE_SUMMARY)
                    ):
                        result = await summarizer.generate_hierarchical_summary(
                            "测试内容", "单章文档"
                        )
                        assert result is not None

    @pytest.mark.asyncio
    async def test_section_merge_fails_fallback(self, summarizer):
        """章节合并失败时回退到直接合并段落摘要"""
        chunks = [MagicMock(title="章A", content="内容A"), MagicMock(title="章B", content="内容B")]

        with patch("dochris.core.text_chunker.structure_aware_split") as mock_split:
            mock_split.return_value = chunks

            with patch.object(
                summarizer,
                "_summarize_chunks_parallel",
                new=AsyncMock(return_value=[SAMPLE_SUMMARY, SAMPLE_SUMMARY]),
            ):
                with patch.object(
                    summarizer,
                    "_group_chunks_by_section",
                    return_value={"章A": [SAMPLE_SUMMARY], "章B": [SAMPLE_SUMMARY]},
                ):
                    with patch.object(
                        summarizer,
                        "_summarize_sections_parallel",
                        new=AsyncMock(return_value=[]),
                    ):
                        with patch.object(
                            summarizer,
                            "_merge_summaries",
                            new=AsyncMock(return_value=SAMPLE_SUMMARY),
                        ):
                            result = await summarizer.generate_hierarchical_summary(
                                "测试内容", "回退文档"
                            )
                            assert result is not None


class TestBuildMessagesEdgeCases:
    """消息构建边界条件"""

    def test_build_chunk_messages_with_empty_content(self, summarizer):
        """空内容的消息构建"""
        messages = summarizer._build_chunk_messages("", "空标题")
        assert len(messages) == 2
        assert "空标题" in messages[1]["content"]

    def test_build_chunk_messages_with_special_chars(self, summarizer):
        """特殊字符的消息构建"""
        messages = summarizer._build_chunk_messages(
            "内容含<script>alert('xss')</script>", "<特殊>标题"
        )
        assert len(messages) == 2

    def test_build_merge_prompt_with_empty_summaries(self, summarizer):
        """空摘要列表的合并 prompt"""
        prompt = summarizer._build_merge_prompt([], "空文档")
        assert "0 个文档片段" in prompt

    def test_build_merge_prompt_with_many_summaries(self, summarizer):
        """大量摘要的合并 prompt"""
        summaries = [
            {
                "one_line": f"摘要{i}",
                "key_points": [],
                "detailed_summary": f"内容{i}",
                "concepts": [],
            }
            for i in range(10)
        ]
        prompt = summarizer._build_merge_prompt(summaries, "大型文档")
        assert "片段 10" in prompt

    def test_build_merge_prompt_qwen3_with_dict_concepts(self, mock_llm_client):
        """qwen3 合并 prompt 处理字典形式概念"""
        mock_llm_client.no_think = True
        summarizer = HierarchicalSummarizer(mock_llm_client)

        summaries = [
            {
                "one_line": "摘要",
                "key_points": ["p1"],
                "detailed_summary": "内容",
                "concepts": [
                    {"name": "概念1", "explanation": "解释1"},
                    {"name": "概念2", "explanation": "解释2"},
                ],
            }
        ]

        prompt = summarizer._build_merge_prompt_qwen3(summaries, "测试")
        assert "概念1" in prompt
        assert "解释1" in prompt

    def test_build_merge_prompt_qwen3_with_string_concepts(self, mock_llm_client):
        """qwen3 合并 prompt 处理字符串形式概念"""
        mock_llm_client.no_think = True
        summarizer = HierarchicalSummarizer(mock_llm_client)

        summaries = [
            {
                "one_line": "摘要",
                "key_points": ["p1"],
                "detailed_summary": "内容",
                "concepts": ["字符串概念1", "字符串概念2"],
            }
        ]

        prompt = summarizer._build_merge_prompt_qwen3(summaries, "测试")
        assert "字符串概念1" in prompt


class TestGroupChunksBySectionEdgeCases:
    """章节分组边界条件"""

    def test_empty_chunks_and_summaries(self, summarizer):
        """空块和空摘要"""
        sections = summarizer._group_chunks_by_section([], [])
        assert sections == {}

    def test_all_untitled_chunks(self, summarizer):
        """所有块无标题"""
        chunks = [MagicMock(title="", content=f"内容{i}") for i in range(3)]
        summaries = [{"one_line": f"摘要{i}"} for i in range(3)]

        sections = summarizer._group_chunks_by_section(chunks, summaries)

        assert "未分类" in sections
        assert len(sections["未分类"]) == 3

    def test_mixed_titled_and_untitled(self, summarizer):
        """混合有标题和无标题块"""
        chunks = [
            MagicMock(title="章A", content="内容"),
            MagicMock(title="", content="内容"),
            MagicMock(title="章A", content="内容"),
        ]
        summaries = [{"one_line": f"摘要{i}"} for i in range(3)]

        sections = summarizer._group_chunks_by_section(chunks, summaries)

        assert "章A" in sections
        assert "未分类" in sections
        assert len(sections["章A"]) == 2
        assert len(sections["未分类"]) == 1


class TestSummarizeSectionsParallel:
    """章节摘要并行处理测试"""

    @pytest.mark.asyncio
    async def test_single_summary_per_section(self, summarizer):
        """每个章节只有一个摘要时直接返回"""
        sections = {"章A": [SAMPLE_SUMMARY], "章B": [SAMPLE_SUMMARY]}

        results = await summarizer._summarize_sections_parallel(sections, "测试", 3)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_exception_in_section(self, summarizer):
        """章节摘要异常时过滤"""
        sections = {"章A": [SAMPLE_SUMMARY, SAMPLE_SUMMARY]}

        with patch.object(
            summarizer, "_merge_summaries", new=AsyncMock(side_effect=Exception("API error"))
        ):
            results = await summarizer._summarize_sections_parallel(sections, "测试", 3)
            assert len(results) == 0


class TestMergeSummariesEdgeCases:
    """合并摘要边界条件"""

    @pytest.mark.asyncio
    async def test_merge_empty_list(self, summarizer):
        """空列表合并返回 None"""
        result = await summarizer._merge_summaries([], "测试", 3)
        assert result is None

    @pytest.mark.asyncio
    async def test_merge_none_element(self, summarizer):
        """包含 None 的列表"""
        # 单个 None 不走 len==1 分支，因为 None != dict
        # None 不等于 summaries[0] 的预期行为取决于实现
        await summarizer._merge_summaries([None], "测试", 3)  # type: ignore
