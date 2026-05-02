"""补充测试 vector/base.py — 覆盖 collection_exists + __repr__"""




class TestBaseVectorStoreConcrete:
    """测试 BaseVectorStore 基类的具体方法"""

    def test_collection_exists_true(self):
        """collection_exists 返回 True"""
        from dochris.vector.base import BaseVectorStore

        class DummyStore(BaseVectorStore):
            name = "dummy"

            def add_documents(self, collection, documents, ids, metadatas=None, **kwargs):
                pass

            def query(self, collection, query_text, n_results=5, **kwargs):
                return []

            def delete(self, collection, ids):
                pass

            def list_collections(self):
                return ["col1", "col2"]

            def get_collection_count(self, collection):
                return 0

        store = DummyStore()
        assert store.collection_exists("col1") is True

    def test_collection_exists_false(self):
        """collection_exists 返回 False"""
        from dochris.vector.base import BaseVectorStore

        class DummyStore(BaseVectorStore):
            name = "dummy"

            def add_documents(self, collection, documents, ids, metadatas=None, **kwargs):
                pass

            def query(self, collection, query_text, n_results=5, **kwargs):
                return []

            def delete(self, collection, ids):
                pass

            def list_collections(self):
                return ["col1"]

            def get_collection_count(self, collection):
                return 0

        store = DummyStore()
        assert store.collection_exists("missing") is False

    def test_repr(self):
        """__repr__ 格式"""
        from dochris.vector.base import BaseVectorStore

        class DummyStore(BaseVectorStore):
            name = "test_store"

            def add_documents(self, collection, documents, ids, metadatas=None, **kwargs):
                pass

            def query(self, collection, query_text, n_results=5, **kwargs):
                return []

            def delete(self, collection, ids):
                pass

            def list_collections(self):
                return []

            def get_collection_count(self, collection):
                return 0

        store = DummyStore()
        assert repr(store) == "DummyStore(name='test_store')"
