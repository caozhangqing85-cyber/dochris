"""补充测试 vector/chromadb_store.py — 覆盖 query exception + list_collections exception"""

from unittest.mock import MagicMock, patch

import pytest


class TestChromaDBStoreExceptions:
    """覆盖异常分支"""

    def test_query_returns_empty_on_exception(self):
        """query 异常时返回空列表"""
        from dochris.vector.chromadb_store import ChromaDBStore

        store = ChromaDBStore()
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.query.side_effect = Exception("DB error")
        mock_client.get_or_create_collection.return_value = mock_collection

        with patch.object(store, "_get_client", return_value=mock_client):
            result = store.query("test_col", "hello")

        assert result == []

    def test_list_collections_returns_empty_on_exception(self):
        """list_collections 异常时返回空列表"""
        from dochris.vector.chromadb_store import ChromaDBStore

        store = ChromaDBStore()
        mock_client = MagicMock()
        mock_client.list_collections.side_effect = Exception("connection failed")

        with patch.object(store, "_get_client", return_value=mock_client):
            result = store.list_collections()

        assert result == []
