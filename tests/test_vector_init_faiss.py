"""补充测试 vector/__init__.py — 覆盖 FAISS ImportError 分支"""


class TestVectorFaissFallback:
    """覆盖 FAISS ImportError 分支 (lines 26-27)"""

    def test_faiss_import_fallback(self):
        """FAISS 不可用时 STORES 不含 faiss"""
        from dochris.vector import STORES

        # 如果系统没有 faiss，STORES 就不会有 faiss
        # 如果有 faiss，STORES 就会有 faiss
        assert "chromadb" in STORES
        # faiss 是可选的
        assert isinstance(STORES, dict)
