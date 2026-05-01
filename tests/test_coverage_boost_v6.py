"""覆盖率提升 v6 — hierarchical_summarizer 同步方法 + phase2 CLI 分支"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# hierarchical_summarizer.py — 同步方法全覆盖
# ============================================================
class TestHierarchicalSummarizerSync:

    def _make_summarizer(self, no_think=False):
        mock_client = MagicMock()
        mock_client.no_think = no_think
        from dochris.core.hierarchical_summarizer import HierarchicalSummarizer
        return HierarchicalSummarizer(mock_client)

    def test_build_chunk_messages_standard(self):
        s = self._make_summarizer(no_think=False)
        msgs = s._build_chunk_messages("some text", "Test Title")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert "JSON" in msgs[0]["content"]
        assert msgs[1]["role"] == "user"
        assert "Test Title" in msgs[1]["content"]

    def test_build_chunk_messages_no_think(self):
        s = self._make_summarizer(no_think=True)
        msgs = s._build_chunk_messages("some text", "Test Title")
        assert len(msgs) == 2
        assert "知识工程师" in msgs[0]["content"]

    def test_build_chunk_messages_qwen3(self):
        s = self._make_summarizer()
        msgs = s._build_chunk_messages_qwen3("hello world", "My Doc")
        assert len(msgs) == 2
        assert "JSON" in msgs[0]["content"]

    def test_build_merge_prompt_standard(self):
        s = self._make_summarizer(no_think=False)
        summaries = [
            {"one_line": "sum1", "key_points": ["p1", "p2"], "detailed_summary": "detail1", "concepts": [{"name": "c1"}]}
        ]
        prompt = s._build_merge_prompt(summaries, "Title")
        assert "Title" in prompt
        assert "片段 1" in prompt
        assert "sum1" in prompt

    def test_build_merge_prompt_no_think(self):
        s = self._make_summarizer(no_think=True)
        summaries = [
            {"one_line": "sum1", "key_points": ["p1"], "detailed_summary": "d1", "concepts": [{"name": "c1", "explanation": "e1"}]}
        ]
        prompt = s._build_merge_prompt(summaries, "Title")
        assert "知识工程师" in prompt
        assert "去重" in prompt

    def test_build_merge_prompt_string_concepts(self):
        s = self._make_summarizer(no_think=False)
        summaries = [
            {"one_line": "s", "key_points": [], "detailed_summary": "d", "concepts": ["string_concept"]}
        ]
        prompt = s._build_merge_prompt(summaries, "T")
        assert "string_concept" in prompt

    def test_build_merge_prompt_qwen3_dict_concepts(self):
        s = self._make_summarizer(no_think=True)
        summaries = [
            {"one_line": "s", "key_points": ["k"], "detailed_summary": "d", "concepts": [{"name": "c", "explanation": "long explanation text here"}]}
        ]
        prompt = s._build_merge_prompt_qwen3(summaries, "Title")
        assert "c" in prompt

    def test_build_merge_prompt_qwen3_string_concepts(self):
        s = self._make_summarizer()
        summaries = [
            {"one_line": "s", "key_points": [], "detailed_summary": "d", "concepts": ["plain_string"]}
        ]
        prompt = s._build_merge_prompt_qwen3(summaries, "T")
        assert "plain_string" in prompt

    def test_group_chunks_by_section_with_title(self):
        s = self._make_summarizer()
        mock_chunks = [MagicMock(title="Section A"), MagicMock(title="Section B"), MagicMock(title="Section A")]
        summaries = [{"id": 1}, {"id": 2}, {"id": 3}]
        result = s._group_chunks_by_section(mock_chunks, summaries)
        assert "Section A" in result
        assert "Section B" in result
        assert len(result["Section A"]) == 2
        assert len(result["Section B"]) == 1

    def test_group_chunks_by_section_no_title(self):
        s = self._make_summarizer()
        mock_chunks = [MagicMock(title=None), MagicMock(title=""), MagicMock(title="Has Title")]
        summaries = [{"id": 1}, {"id": 2}, {"id": 3}]
        result = s._group_chunks_by_section(mock_chunks, summaries)
        assert "未分类" in result
        assert len(result["未分类"]) == 2


# ============================================================
# phase2_compilation.py — CLI 分支
# ============================================================
class TestPhase2CompilationCLI:

    def test_main_no_api_key(self):
        import dochris.phases.phase2_compilation as p2
        with patch("sys.argv", ["phase2_compilation.py"]), \
             patch("dochris.phases.phase2_compilation.DEFAULT_API_KEY", ""):
            with pytest.raises(SystemExit):
                p2.main()

    def test_main_clear_cache(self):
        import dochris.phases.phase2_compilation as p2
        with patch("sys.argv", ["phase2_compilation.py", "--clear-cache"]), \
             patch("dochris.phases.phase2_compilation.clear_cache", return_value=5), \
             patch("dochris.phases.phase2_compilation.get_default_workspace", return_value=Path("/tmp/ws")):
            p2.main()

    def test_main_clear_all_cache(self):
        import dochris.phases.phase2_compilation as p2
        with patch("sys.argv", ["phase2_compilation.py", "--clear-all-cache"]), \
             patch("dochris.phases.phase2_compilation.clear_cache", return_value=10), \
             patch("dochris.phases.phase2_compilation.get_default_workspace", return_value=Path("/tmp/ws")):
            p2.main()

    def test_main_with_concurrency(self):
        import dochris.phases.phase2_compilation as p2
        with patch("sys.argv", ["phase2_compilation.py", "--concurrency", "2", "--clear-cache"]), \
             patch("dochris.phases.phase2_compilation.clear_cache", return_value=0), \
             patch("dochris.phases.phase2_compilation.get_default_workspace", return_value=Path("/tmp/ws")):
            p2.main()
