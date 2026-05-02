"""向量存储读写性能基准测试

测试 ChromaDB 向量存储的增删查性能（使用内存模式）。
"""

from unittest.mock import MagicMock

import pytest


class TestVectorPerformance:
    """向量存储性能基准"""

    def _make_store(self) -> "ChromaDBStore":
        """创建 mock-backed ChromaDBStore"""
        from dochris.vector.chromadb_store import ChromaDBStore

        store = ChromaDBStore()
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["doc-1", "doc-2", "doc-3", "doc-4", "doc-5"]],
            "documents": [["内容1", "内容2", "内容3", "内容4", "内容5"]],
            "distances": [[0.1, 0.2, 0.3, 0.4, 0.5]],
            "metadatas": [[{"source": "test"}] * 5],
        }
        mock_client.get_or_create_collection.return_value = mock_collection
        store._client = mock_client
        return store

    def test_add_documents_mock(self, benchmark) -> None:
        """文档添加性能（mock ChromaDB）"""
        store = self._make_store()

        docs = [f"文档内容 {i}，包含测试数据。" for i in range(100)]
        ids = [f"doc-{i}" for i in range(100)]
        metas = [{"source": f"test-{i}"} for i in range(100)]

        benchmark(store.add_documents, "test_collection", docs, ids, metas)

    def test_query_mock(self, benchmark) -> None:
        """查询性能（mock ChromaDB）"""
        store = self._make_store()

        result = benchmark(store.query, "test_collection", "搜索查询", n_results=5)
        assert isinstance(result, list)

    def test_list_collections_mock(self, benchmark) -> None:
        """列出集合性能（mock ChromaDB）"""
        store = self._make_store()

        mock_c1 = MagicMock()
        mock_c1.name = "summaries"
        mock_c2 = MagicMock()
        mock_c2.name = "concepts"
        store._client.list_collections.return_value = [mock_c1, mock_c2]

        result = benchmark(store.list_collections)
        assert len(result) == 2

    def test_batch_add_performance(self, benchmark) -> None:
        """批量添加性能（mock ChromaDB）"""
        store = self._make_store()

        docs = [f"批量文档 {i}" for i in range(500)]
        ids = [f"batch-{i}" for i in range(500)]

        benchmark(store.add_documents, "batch_test", docs, ids)
