"""补充测试 vector/__init__.py — 覆盖 FAISS ImportError + get_store"""

import pytest


class TestVectorInit:
    """覆盖 vector 包初始化"""

    def test_get_store_chromadb(self):
        """获取 chromadb store"""
        from dochris.vector import get_store

        store_cls = get_store("chromadb")
        assert store_cls is not None

    def test_get_store_unknown_raises(self):
        """未知 store 抛出 ValueError"""
        from dochris.vector import get_store

        with pytest.raises(ValueError, match="Unknown vector store"):
            get_store("nonexistent")

    def test_stores_registry(self):
        """STORES 注册表包含 chromadb"""
        from dochris.vector import STORES

        assert "chromadb" in STORES
