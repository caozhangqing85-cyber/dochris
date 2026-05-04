#!/usr/bin/env python3
"""测试向量存储抽象层"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from dochris.vector.base import BaseVectorStore
from dochris.vector.chromadb_store import ChromaDBStore
from dochris.vector.faiss_store import FAISSStore


class TestBaseVectorStore:
    """测试 BaseVectorStore 抽象基类"""

    def test_cannot_instantiate_base_class(self) -> None:
        """验证不能直接实例化基类"""
        with pytest.raises(TypeError, match="abstract"):
            BaseVectorStore()

    def test_abstract_methods_exist(self) -> None:
        """验证抽象方法存在"""
        abstract_methods = BaseVectorStore.__abstractmethods__
        expected = {"add_documents", "query", "delete", "list_collections", "get_collection_count"}
        assert abstract_methods == expected

    def test_collection_exists_default_implementation(self) -> None:
        """测试 collection_exists 默认实现"""

        class ConcreteStore(BaseVectorStore):
            name = "concrete"

            def add_documents(self, collection, documents, ids, metadatas=None):
                pass

            def query(self, collection, query_text, n_results=5, where=None, **kwargs):
                return []

            def delete(self, collection, ids):
                pass

            def list_collections(self):
                return ["col1", "col2"]

            def get_collection_count(self, collection):
                return 0

        store = ConcreteStore()
        assert store.collection_exists("col1") is True
        assert store.collection_exists("col3") is False

    def test_repr(self) -> None:
        """测试 __repr__ 实现"""

        class ConcreteStore(BaseVectorStore):
            name = "test_store"

            def add_documents(self, collection, documents, ids, metadatas=None):
                pass

            def query(self, collection, query_text, n_results=5, where=None, **kwargs):
                return []

            def delete(self, collection, ids):
                pass

            def list_collections(self):
                return []

            def get_collection_count(self, collection):
                return 0

        store = ConcreteStore()
        assert repr(store) == "ConcreteStore(name='test_store')"


class TestVectorStoreRegistry:
    """测试向量存储注册表"""

    def test_stores_has_chromadb(self) -> None:
        """验证 STORES 包含 chromadb"""
        from dochris.vector import STORES

        assert "chromadb" in STORES
        assert STORES["chromadb"] == ChromaDBStore

    def test_get_store_chromadb(self) -> None:
        """验证 get_store('chromadb') 返回正确类"""
        from dochris.vector import get_store

        store_cls = get_store("chromadb")
        assert store_cls == ChromaDBStore

    def test_get_store_unknown_raises_value_error(self) -> None:
        """验证 get_store('unknown') 抛出 ValueError"""
        from dochris.vector import get_store

        with pytest.raises(ValueError, match="Unknown vector store.*unknown"):
            get_store("unknown")

    def test_get_store_error_message_shows_available(self) -> None:
        """验证错误消息包含可用存储列表"""
        from dochris.vector import get_store

        with pytest.raises(ValueError) as exc_info:
            get_store("fake_store")
        assert "chromadb" in str(exc_info.value)


class TestChromaDBStore:
    """测试 ChromaDBStore 实现"""

    def test_name(self) -> None:
        """验证 name 属性"""
        assert ChromaDBStore.name == "chromadb"

    def test_init_without_persist_directory(self) -> None:
        """测试不指定持久化目录的初始化"""
        store = ChromaDBStore()
        assert store._persist_directory is None
        assert store._client is None

    def test_init_with_persist_directory(self) -> None:
        """测试指定持久化目录的初始化"""
        store = ChromaDBStore(persist_directory="/tmp/test")
        assert str(store._persist_directory) == "/tmp/test"
        assert store._client is None

    def test_get_client_creates_persistent_client(self) -> None:
        """测试 _get_client 创建 PersistentClient"""
        mock_client = MagicMock()
        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = mock_client

        with patch.dict("sys.modules", {"chromadb": mock_chromadb}):
            store = ChromaDBStore(persist_directory="/tmp/test")
            client = store._get_client()

            assert client == mock_client
            mock_chromadb.PersistentClient.assert_called_once_with(path="/tmp/test")
            assert store._client == mock_client

    def test_get_client_creates_memory_client(self) -> None:
        """测试无持久化目录时创建内存客户端"""
        mock_client = MagicMock()
        mock_chromadb = MagicMock()
        mock_chromadb.Client.return_value = mock_client

        with patch.dict("sys.modules", {"chromadb": mock_chromadb}):
            store = ChromaDBStore()
            client = store._get_client()

            assert client == mock_client
            mock_chromadb.Client.assert_called_once()
            assert store._client == mock_client

    def test_get_client_raises_import_error_when_not_installed(self) -> None:
        """测试 chromadb 未安装时抛出 ImportError"""
        with patch.dict("sys.modules", {"chromadb": None}):
            store = ChromaDBStore()

            with pytest.raises(ImportError, match="chromadb not installed"):
                store._get_client()

    def test_add_documents(self) -> None:
        """测试添加文档"""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = mock_client

        with patch.dict("sys.modules", {"chromadb": mock_chromadb}):
            store = ChromaDBStore(persist_directory="/tmp/test")
            store.add_documents(
                collection="test_col",
                documents=["doc1", "doc2"],
                ids=["id1", "id2"],
                metadatas=[{"key": "value1"}, {"key": "value2"}],
            )

            mock_collection.add.assert_called_once_with(
                documents=["doc1", "doc2"],
                ids=["id1", "id2"],
                metadatas=[{"key": "value1"}, {"key": "value2"}],
            )

    def test_add_documents_without_metadatas(self) -> None:
        """测试添加文档（无元数据）"""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = mock_client

        with patch.dict("sys.modules", {"chromadb": mock_chromadb}):
            store = ChromaDBStore(persist_directory="/tmp/test")
            store.add_documents(
                collection="test_col",
                documents=["doc1"],
                ids=["id1"],
            )

            mock_collection.add.assert_called_once_with(
                documents=["doc1"], ids=["id1"], metadatas=[{}]
            )

    def test_add_documents_validates_length(self) -> None:
        """验证 documents 和 ids 长度不匹配时抛出 ValueError"""
        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = MagicMock()

        with patch.dict("sys.modules", {"chromadb": mock_chromadb}):
            store = ChromaDBStore(persist_directory="/tmp/test")

            with pytest.raises(ValueError, match="documents.*and ids.*length mismatch"):
                store.add_documents(
                    collection="test_col",
                    documents=["doc1", "doc2"],
                    ids=["id1"],
                )

    def test_add_documents_validates_metadatas_length(self) -> None:
        """验证 metadatas 长度不匹配时抛出 ValueError"""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = mock_client

        with patch.dict("sys.modules", {"chromadb": mock_chromadb}):
            store = ChromaDBStore(persist_directory="/tmp/test")

            with pytest.raises(ValueError, match="metadatas.*and documents.*length mismatch"):
                store.add_documents(
                    collection="test_col",
                    documents=["doc1", "doc2"],
                    ids=["id1", "id2"],
                    metadatas=[{"key": "value"}],
                )

    def test_query_returns_results(self) -> None:
        """测试查询返回结果"""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["id1", "id2"]],
            "documents": [["doc1", "doc2"]],
            "metadatas": [[{"key": "value1"}, {"key": "value2"}]],
            "distances": [[0.1, 0.2]],
        }
        mock_client.get_collection.return_value = mock_collection
        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = mock_client

        with patch.dict("sys.modules", {"chromadb": mock_chromadb}):
            store = ChromaDBStore(persist_directory="/tmp/test")
            results = store.query("test_col", "search query", n_results=5)

            assert len(results) == 2
            assert results[0] == {
                "id": "id1",
                "document": "doc1",
                "metadata": {"key": "value1"},
                "distance": 0.1,
            }
            assert results[1] == {
                "id": "id2",
                "document": "doc2",
                "metadata": {"key": "value2"},
                "distance": 0.2,
            }
            mock_collection.query.assert_called_once_with(
                query_texts=["search query"], n_results=5, where=None
            )

    def test_query_with_where_filter(self) -> None:
        """测试带 where 过滤的查询"""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }
        mock_client.get_collection.return_value = mock_collection
        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = mock_client

        with patch.dict("sys.modules", {"chromadb": mock_chromadb}):
            store = ChromaDBStore(persist_directory="/tmp/test")
            store.query("test_col", "search query", where={"category": "tech"})

            mock_collection.query.assert_called_once_with(
                query_texts=["search query"], n_results=5, where={"category": "tech"}
            )

    def test_query_collection_not_found_returns_empty(self) -> None:
        """测试查询不存在的集合返回空列表"""
        mock_client = MagicMock()
        mock_client.get_collection.side_effect = Exception("Not found")
        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = mock_client

        with patch.dict("sys.modules", {"chromadb": mock_chromadb}):
            store = ChromaDBStore(persist_directory="/tmp/test")
            results = store.query("nonexistent", "search query")

            assert results == []

    def test_delete(self) -> None:
        """测试删除文档"""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_collection.return_value = mock_collection
        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = mock_client

        with patch.dict("sys.modules", {"chromadb": mock_chromadb}):
            store = ChromaDBStore(persist_directory="/tmp/test")
            store.delete("test_col", ["id1", "id2"])

            mock_collection.delete.assert_called_once_with(ids=["id1", "id2"])

    def test_delete_nonexistent_collection_no_error(self) -> None:
        """测试删除不存在的集合不抛出错误"""
        mock_client = MagicMock()
        mock_client.get_collection.side_effect = Exception("Not found")
        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = mock_client

        with patch.dict("sys.modules", {"chromadb": mock_chromadb}):
            store = ChromaDBStore(persist_directory="/tmp/test")
            store.delete("nonexistent", ["id1"])  # 不应抛出错误

    def test_list_collections(self) -> None:
        """测试列出集合"""
        mock_client = MagicMock()
        mock_col1 = MagicMock()
        mock_col1.name = "col1"
        mock_col2 = MagicMock()
        mock_col2.name = "col2"
        mock_client.list_collections.return_value = [mock_col1, mock_col2]
        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = mock_client

        with patch.dict("sys.modules", {"chromadb": mock_chromadb}):
            store = ChromaDBStore(persist_directory="/tmp/test")
            collections = store.list_collections()

            assert collections == ["col1", "col2"]

    def test_get_collection_count(self) -> None:
        """测试获取集合文档数量"""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 42
        mock_client.get_collection.return_value = mock_collection
        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = mock_client

        with patch.dict("sys.modules", {"chromadb": mock_chromadb}):
            store = ChromaDBStore(persist_directory="/tmp/test")
            count = store.get_collection_count("test_col")

            assert count == 42

    def test_get_collection_count_nonexistent_returns_zero(self) -> None:
        """测试获取不存在集合的文档数量返回 0"""
        mock_client = MagicMock()
        mock_client.get_collection.side_effect = Exception("Not found")
        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = mock_client

        with patch.dict("sys.modules", {"chromadb": mock_chromadb}):
            store = ChromaDBStore(persist_directory="/tmp/test")
            count = store.get_collection_count("nonexistent")

            assert count == 0

    def test_close(self) -> None:
        """测试 close 清理资源"""
        mock_client = MagicMock()
        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = mock_client

        with patch.dict("sys.modules", {"chromadb": mock_chromadb}):
            store = ChromaDBStore(persist_directory="/tmp/test")
            store._get_client()
            assert store._client is not None

            store.close()
            assert store._client is None


class TestFAISSStore:
    """测试 FAISSStore 实现"""

    def test_name(self) -> None:
        """验证 name 属性"""
        assert FAISSStore.name == "faiss"

    def test_init_with_defaults(self) -> None:
        """测试默认参数初始化"""
        store = FAISSStore()
        assert "faiss_data" in str(store._persist_directory)
        assert store._embedding_model_name == "all-MiniLM-L6-v2"
        assert store._model is None
        assert store._indexes == {}
        assert store._documents == {}
        assert store._metadatas == {}

    def test_init_with_custom_params(self) -> None:
        """测试自定义参数初始化"""
        store = FAISSStore(persist_directory="/tmp/faiss", embedding_model="custom-model")
        assert str(store._persist_directory) == "/tmp/faiss"
        assert store._embedding_model_name == "custom-model"

    def test_get_model_raises_import_error_when_not_installed(self) -> None:
        """测试 sentence-transformers 未安装时抛出 ImportError"""
        store = FAISSStore()

        with patch.dict("sys.modules", {"sentence_transformers": None}):
            with pytest.raises(ImportError, match="sentence-transformers not installed"):
                store._get_model()

    def test_get_model_creates_model(self) -> None:
        """测试 _get_model 创建嵌入模型"""
        mock_model = MagicMock()
        mock_sentence_transformers = MagicMock()
        mock_sentence_transformers.SentenceTransformer = MagicMock(return_value=mock_model)

        with patch.dict("sys.modules", {"sentence_transformers": mock_sentence_transformers}):
            store = FAISSStore()
            model = store._get_model()

            assert model == mock_model
            mock_sentence_transformers.SentenceTransformer.assert_called_once_with(
                "all-MiniLM-L6-v2"
            )
            assert store._model == mock_model

    def test_get_index_path(self) -> None:
        """测试 _get_index_path"""
        store = FAISSStore(persist_directory="/tmp/faiss")
        path = store._get_index_path("my_collection")

        assert path == store._persist_directory / "my_collection"

    def test_load_collection_creates_new_when_not_exists(self) -> None:
        """测试加载不存在的集合"""
        mock_persist_dir = MagicMock()
        mock_persist_dir.exists.return_value = False

        with patch("dochris.vector.faiss_store.Path", return_value=mock_persist_dir):
            store = FAISSStore()
            store._load_collection("new_collection")

            assert store._indexes["new_collection"] is None
            assert store._documents["new_collection"] == {}
            assert store._metadatas["new_collection"] == {}

    def test_add_documents_raises_import_error_when_faiss_not_installed(self) -> None:
        """测试 faiss 未安装时抛出 ImportError"""
        with patch.dict("sys.modules", {"faiss": None}):
            store = FAISSStore()

            with pytest.raises(ImportError, match="faiss not installed"):
                store.add_documents("test_col", ["doc1"], ["id1"])

    def test_add_documents(self) -> None:
        """测试添加文档"""
        mock_model = MagicMock()
        mock_embeddings = MagicMock()
        mock_embeddings.shape = (2, 384)
        mock_embeddings.astype.return_value = mock_embeddings
        mock_model.encode.return_value = mock_embeddings

        mock_transformer = MagicMock()
        mock_transformer.SentenceTransformer.return_value = mock_model

        mock_index = MagicMock()
        mock_index.ntotal = 0
        mock_faiss = MagicMock()
        mock_faiss.IndexFlatL2.return_value = mock_index

        with patch.dict(
            "sys.modules", {"faiss": mock_faiss, "sentence_transformers": mock_transformer}
        ):
            store = FAISSStore()
            store.add_documents(
                collection="test_col",
                documents=["doc1", "doc2"],
                ids=["id1", "id2"],
                metadatas=[{"key": "value1"}, {"key": "value2"}],
            )

            mock_model.encode.assert_called_once_with(["doc1", "doc2"])
            mock_index.add.assert_called_once()
            assert "test_col" in store._documents
            assert store._documents["test_col"]["id1"] == "doc1"
            assert store._documents["test_col"]["id2"] == "doc2"

    def test_add_documents_validates_length(self) -> None:
        """验证 documents 和 ids 长度不匹配时抛出 ValueError"""
        mock_model = MagicMock()
        mock_transformer = MagicMock()
        mock_transformer.SentenceTransformer.return_value = mock_model
        mock_faiss = MagicMock()

        with patch.dict(
            "sys.modules", {"faiss": mock_faiss, "sentence_transformers": mock_transformer}
        ):
            store = FAISSStore()

            with pytest.raises(ValueError, match="documents.*and ids.*length mismatch"):
                store.add_documents("test_col", documents=["doc1", "doc2"], ids=["id1"])

    def test_query_returns_empty_when_no_documents(self) -> None:
        """测试查询空集合返回空列表"""
        mock_model = MagicMock()
        mock_transformer = MagicMock()
        mock_transformer.SentenceTransformer.return_value = mock_model
        mock_faiss = MagicMock()

        with patch.dict(
            "sys.modules", {"faiss": mock_faiss, "sentence_transformers": mock_transformer}
        ):
            store = FAISSStore()
            results = store.query("empty_col", "search query")

            assert results == []

    def test_query(self) -> None:
        """测试查询返回结果"""
        import numpy as np

        mock_model = MagicMock()
        mock_query_emb = np.array([[0.1, 0.2, 0.3]], dtype="float32")
        mock_model.encode.return_value = mock_query_emb

        mock_sentence_transformers = MagicMock()
        mock_sentence_transformers.SentenceTransformer.return_value = mock_model

        mock_index = MagicMock()
        mock_index.ntotal = 2
        # 返回 distances 和 indices 数组
        distances = np.array([[0.1, 0.2]], dtype="float32")
        indices = np.array([[0, 1]], dtype="int64")
        mock_index.search.return_value = (distances, indices)

        mock_faiss = MagicMock()
        mock_faiss.IndexFlatL2.return_value = mock_index

        with patch.dict(
            "sys.modules",
            {"faiss": mock_faiss, "sentence_transformers": mock_sentence_transformers},
        ):
            store = FAISSStore()
            # 模拟已加载的文档
            store._documents["test_col"] = {"id1": "doc1", "id2": "doc2"}
            store._metadatas["test_col"] = {"id1": {"key": "value1"}, "id2": {"key": "value2"}}
            store._indexes["test_col"] = mock_index

            results = store.query("test_col", "search query", n_results=5)

            assert len(results) == 2
            assert results[0]["id"] == "id1"
            assert results[0]["document"] == "doc1"
            assert results[0]["metadata"] == {"key": "value1"}
            assert abs(results[0]["distance"] - 0.1) < 0.001  # 浮点数精度容差

    def test_query_with_where_filter(self) -> None:
        """测试带 where 过滤的查询"""
        import numpy as np

        mock_model = MagicMock()
        mock_query_emb = np.array([[0.1, 0.2, 0.3]], dtype="float32")
        mock_model.encode.return_value = mock_query_emb

        mock_sentence_transformers = MagicMock()
        mock_sentence_transformers.SentenceTransformer.return_value = mock_model

        mock_index = MagicMock()
        mock_index.ntotal = 2
        distances = np.array([[0.1, 0.2]], dtype="float32")
        indices = np.array([[0, 1]], dtype="int64")
        mock_index.search.return_value = (distances, indices)

        mock_faiss = MagicMock()
        mock_faiss.IndexFlatL2.return_value = mock_index

        with patch.dict(
            "sys.modules",
            {"faiss": mock_faiss, "sentence_transformers": mock_sentence_transformers},
        ):
            store = FAISSStore()
            store._documents["test_col"] = {"id1": "doc1", "id2": "doc2"}
            store._metadatas["test_col"] = {
                "id1": {"category": "tech"},
                "id2": {"category": "other"},
            }
            store._indexes["test_col"] = mock_index

            results = store.query("test_col", "search query", where={"category": "tech"})

            # 只有 id1 匹配过滤条件
            assert len(results) == 1
            assert results[0]["id"] == "id1"

    def test_delete_rebuilds_index(self) -> None:
        """测试删除文档重建索引"""
        import numpy as np

        mock_model = MagicMock()
        mock_embeddings = np.array([[0.1, 0.2]], dtype="float32")
        mock_model.encode.return_value = mock_embeddings

        mock_sentence_transformers = MagicMock()
        mock_sentence_transformers.SentenceTransformer.return_value = mock_model

        mock_index = MagicMock()
        mock_index.ntotal = 0  # 让它看起来是空索引
        mock_faiss = MagicMock()
        mock_faiss.IndexFlatL2.return_value = mock_index

        with patch.dict(
            "sys.modules",
            {"faiss": mock_faiss, "sentence_transformers": mock_sentence_transformers},
        ):
            store = FAISSStore()
            store._documents["test_col"] = {"id1": "doc1", "id2": "doc2", "id3": "doc3"}
            store._metadatas["test_col"] = {
                "id1": {"key": "v1"},
                "id2": {"key": "v2"},
                "id3": {"key": "v3"},
            }
            store._indexes["test_col"] = mock_index

            # 删除 id2
            store.delete("test_col", ["id2"])

            # 验证重建后索引只保留 id1 和 id3
            assert "id2" not in store._documents.get("test_col", {})

    def test_list_collections(self) -> None:
        """测试列出集合"""
        mock_persist_dir = MagicMock()
        mock_dir1 = MagicMock()
        mock_dir1.name = "col1"
        mock_dir1.is_dir.return_value = True
        mock_dir1.__truediv__.return_value.exists.return_value = True

        mock_dir2 = MagicMock()
        mock_dir2.name = "col2"
        mock_dir2.is_dir.return_value = True
        mock_dir2.__truediv__.return_value.exists.return_value = True

        mock_persist_dir.iterdir.return_value = [mock_dir1, mock_dir2]
        mock_persist_dir.exists.return_value = True

        with patch("dochris.vector.faiss_store.Path", return_value=mock_persist_dir):
            store = FAISSStore()
            collections = store.list_collections()

            assert collections == ["col1", "col2"]

    def test_list_collections_empty_when_not_exists(self) -> None:
        """测试持久化目录不存在时返回空列表"""
        mock_persist_dir = MagicMock()
        mock_persist_dir.exists.return_value = False

        with patch("dochris.vector.faiss_store.Path", return_value=mock_persist_dir):
            store = FAISSStore()
            collections = store.list_collections()

            assert collections == []

    def test_get_collection_count(self) -> None:
        """测试获取集合文档数量"""
        mock_index = MagicMock()
        mock_index.ntotal = 10
        mock_faiss = MagicMock()
        mock_faiss.IndexFlatL2.return_value = mock_index

        with patch.dict("sys.modules", {"faiss": mock_faiss}):
            store = FAISSStore()
            store._indexes["test_col"] = mock_index

            count = store.get_collection_count("test_col")

            assert count == 10

    def test_get_collection_count_no_index(self) -> None:
        """测试获取不存在集合的文档数量返回 0"""
        store = FAISSStore()
        count = store.get_collection_count("nonexistent")

        assert count == 0

    def test_close(self) -> None:
        """测试 close 清理资源"""
        store = FAISSStore()
        store._indexes["test"] = MagicMock()
        store._documents["test"] = {"id": "doc"}
        store._metadatas["test"] = {"id": {}}
        store._model = MagicMock()

        store.close()

        assert store._indexes == {}
        assert store._documents == {}
        assert store._metadatas == {}
        assert store._model is None
