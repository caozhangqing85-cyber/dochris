"""补充测试 hierarchical_summarizer.py — 覆盖 generate_hierarchical_summary 的过滤和回退路径"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestHierarchicalFallbackPaths:
    """覆盖 generate_hierarchical_summary 中异常过滤和合并"""

    @pytest.mark.asyncio
    async def test_generate_hierarchical_filters_exceptions(self):
        """异常结果被过滤，有效结果继续合并"""
        from dochris.core.hierarchical_summarizer import HierarchicalSummarizer

        mock_client = MagicMock()
        summarizer = HierarchicalSummarizer(mock_client)

        mixed_results = [{"summary": "valid"}, RuntimeError("failed"), None]

        with patch.object(summarizer, "_summarize_chunks_parallel", new_callable=AsyncMock, return_value=mixed_results):
            with patch.object(summarizer, "_group_chunks_by_section", return_value={"section1": []}):
                with patch.object(summarizer, "_merge_summaries", new_callable=AsyncMock, return_value={"merged": True}):
                    with patch("dochris.core.text_chunker.structure_aware_split", return_value=[MagicMock()]):
                        result = await summarizer.generate_hierarchical_summary("test content", "Test Title")

        assert result == {"merged": True}

    @pytest.mark.asyncio
    async def test_generate_hierarchical_all_fail(self):
        """所有分块摘要失败返回 None"""
        from dochris.core.hierarchical_summarizer import HierarchicalSummarizer

        mock_client = MagicMock()
        summarizer = HierarchicalSummarizer(mock_client)

        with patch.object(summarizer, "_summarize_chunks_parallel", new_callable=AsyncMock, return_value=[]):
            with patch("dochris.core.text_chunker.structure_aware_split", return_value=[MagicMock()]):
                result = await summarizer.generate_hierarchical_summary("test content", "Test Title")

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_hierarchical_multi_section(self):
        """多章节时先做章节摘要再合并"""
        from dochris.core.hierarchical_summarizer import HierarchicalSummarizer

        mock_client = MagicMock()
        summarizer = HierarchicalSummarizer(mock_client)

        chunk_summaries = [{"summary": "s1"}, {"summary": "s2"}]
        sections = {"section1": [{"summary": "s1"}], "section2": [{"summary": "s2"}]}
        section_summaries = [{"summary": "sec1"}, {"summary": "sec2"}]

        with patch.object(summarizer, "_summarize_chunks_parallel", new_callable=AsyncMock, return_value=chunk_summaries):
            with patch.object(summarizer, "_group_chunks_by_section", return_value=sections):
                with patch.object(summarizer, "_summarize_sections_parallel", new_callable=AsyncMock, return_value=section_summaries):
                    with patch.object(summarizer, "_merge_summaries", new_callable=AsyncMock, return_value={"final": True}):
                        with patch("dochris.core.text_chunker.structure_aware_split", return_value=[MagicMock()]):
                            result = await summarizer.generate_hierarchical_summary("test content", "Test Title")

        assert result == {"final": True}
