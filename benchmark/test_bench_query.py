"""查询性能基准测试

测试知识库查询各阶段的性能：
- 关键词搜索
- 向量检索
- 概念/摘要提取
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestQueryPerformance:
    """查询引擎性能基准"""

    def test_keyword_search(
        self, benchmark, sample_text_medium: str, tmp_path: Path
    ) -> None:
        """关键词搜索性能"""
        from dochris.phases.query_utils import _keyword_search

        wiki_dir = tmp_path / "wiki" / "summaries"
        wiki_dir.mkdir(parents=True, exist_ok=True)
        for i in range(20):
            f = wiki_dir / f"test-{i}.md"
            f.write_text(sample_text_medium)

        def mock_extract(file_path: Path, text: str) -> dict:
            return {"title": "测试", "content": text[:100]}

        benchmark(
            _keyword_search,
            query="技术",
            search_dir=wiki_dir,
            top_k=5,
            extract_fn=mock_extract,
            source_label="wiki",
        )

    def test_extract_summary(self, benchmark) -> None:
        """摘要提取性能"""
        from dochris.phases.query_utils import _extract_summary

        text = "# 测试摘要\n\n" + "这是测试内容，包含技术关键词。" * 50
        f = Path("/tmp/bench_summary.md")
        result = benchmark(_extract_summary, f, text)
        assert result is not None

    def test_extract_concept(self, benchmark) -> None:
        """概念提取性能"""
        from dochris.phases.query_utils import _extract_concept

        text = "# 测试概念\n\n" + "这是概念定义和详细描述。" * 20
        f = Path("/tmp/bench_concept.md")
        result = benchmark(_extract_concept, f, text)
        assert result is not None

    def test_vector_store_mock(self, benchmark) -> None:
        """向量检索性能（mock 嵌入）"""
        from dochris.vector.chromadb_store import ChromaDBStore

        store = ChromaDBStore()
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["doc-1", "doc-2", "doc-3"]],
            "documents": [["内容1", "内容2", "内容3"]],
            "distances": [[0.1, 0.2, 0.3]],
        }
        mock_client.get_or_create_collection.return_value = mock_collection
        store._client = mock_client

        result = benchmark(store.query, "test_col", "测试查询", n_results=3)
        assert isinstance(result, list)
