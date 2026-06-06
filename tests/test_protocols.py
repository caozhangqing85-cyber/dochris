"""
测试 protocols.py 模块
"""

from typing import Any

import pytest


class TestProtocolsModule:
    """测试接口协议模块"""

    def test_protocols_module_exists(self):
        """测试协议模块可以导入"""
        from dochris import protocols

        assert protocols is not None

    def test_llm_provider_protocol(self):
        """测试 LLMProvider 协议"""
        from dochris.protocols import LLMProvider

        # 创建一个符合 LLMProvider 协议的实现类
        class MockLLM:
            async def generate(
                self,
                prompt: str,
                system_prompt: str | None = None,
                max_tokens: int = 4000,
                temperature: float = 0.7,
                **kwargs: Any,
            ) -> str:
                return "response"

            async def close(self) -> None:
                pass

        mock = MockLLM()
        # 使用 isinstance 检查协议兼容性（因为使用了 @runtime_checkable）
        assert isinstance(mock, LLMProvider)

    def test_vector_store_protocol(self):
        """测试 VectorStore 协议（已对齐 BaseVectorStore ABC）"""
        from dochris.protocols import VectorStore

        class MockVectorStore:
            def add_documents(
                self,
                collection: str,
                documents: list[str],
                ids: list[str],
                metadatas: list[dict[str, Any]] | None = None,
            ) -> None:
                pass

            def query(
                self,
                collection: str,
                query_text: str,
                n_results: int = 5,
                where: dict[str, Any] | None = None,
                **kwargs: Any,
            ) -> list[dict[str, Any]]:
                return []

            def delete(self, collection: str, ids: list[str]) -> None:
                pass

            def list_collections(self) -> list[str]:
                return ["collection1"]

            def get_collection_count(self, collection: str) -> int:
                return 0

        mock = MockVectorStore()
        assert isinstance(mock, VectorStore)

    def test_file_parser_protocol(self):
        """测试 FileParser 协议"""
        from dochris.protocols import FileParser

        class MockParser:
            def supported_extensions(self) -> list[str]:
                return [".txt", ".md"]

            def parse(self, file_path: str, **kwargs: Any) -> str:
                return "parsed content"

        mock = MockParser()
        assert isinstance(mock, FileParser)

    def test_quality_scorer_protocol(self):
        """测试 QualityScorer 协议"""
        from dochris.protocols import QualityScorer

        class MockScorer:
            def score(self, text: str, metadata: dict[str, Any] | None = None) -> float:
                return 85.0

        mock = MockScorer()
        assert isinstance(mock, QualityScorer)

    def test_llm_provider_has_required_methods(self):
        """测试 LLMProvider 有必需的方法"""
        from dochris.protocols import LLMProvider

        # 检查协议定义了正确的方法
        assert hasattr(LLMProvider, "generate")
        assert hasattr(LLMProvider, "close")

    def test_vector_store_has_required_methods(self):
        """测试 VectorStore 有必需的方法（已对齐 BaseVectorStore ABC）"""
        from dochris.protocols import VectorStore

        assert hasattr(VectorStore, "add_documents")
        assert hasattr(VectorStore, "query")
        assert hasattr(VectorStore, "delete")
        assert hasattr(VectorStore, "list_collections")
        assert hasattr(VectorStore, "get_collection_count")

    def test_file_parser_has_required_methods(self):
        """测试 FileParser 有必需的方法"""
        from dochris.protocols import FileParser

        assert hasattr(FileParser, "supported_extensions")
        assert hasattr(FileParser, "parse")

    def test_quality_scorer_has_required_methods(self):
        """测试 QualityScorer 有必需的方法"""
        from dochris.protocols import QualityScorer

        assert hasattr(QualityScorer, "score")


class TestProtocolUsage:
    """测试协议使用示例"""

    @pytest.mark.asyncio
    async def test_concrete_llm_implementation(self):
        """测试具体的 LLM 实现"""

        class ConcreteLLM:
            async def generate(
                self,
                prompt: str,
                system_prompt: str | None = None,
                max_tokens: int = 4000,
                temperature: float = 0.7,
                **kwargs: Any,
            ) -> str:
                return f"Generated: {prompt[:50]}"

            async def close(self) -> None:
                pass

        llm = ConcreteLLM()
        result = await llm.generate("test prompt")
        assert "test prompt" in result
        await llm.close()

    def test_concrete_vector_store_implementation(self):
        """测试具体的向量存储实现（已对齐 BaseVectorStore ABC）"""

        class SimpleVectorStore:
            def __init__(self):
                self.data: dict[str, dict[str, Any]] = {}

            def add_documents(
                self,
                collection: str,
                documents: list[str],
                ids: list[str],
                metadatas: list[dict[str, Any]] | None = None,
            ) -> None:
                if collection not in self.data:
                    self.data[collection] = {}
                for doc_id, doc in zip(ids, documents, strict=True):
                    self.data[collection][doc_id] = {"text": doc}

            def query(
                self,
                collection: str,
                query_text: str,
                n_results: int = 5,
                where: dict[str, Any] | None = None,
                **kwargs: Any,
            ) -> list[dict[str, Any]]:
                return [{"id": k, "text": v["text"]} for k, v in self.data.get(collection, {}).items()]

            def delete(self, collection: str, ids: list[str]) -> None:
                for doc_id in ids:
                    self.data.get(collection, {}).pop(doc_id, None)

            def list_collections(self) -> list[str]:
                return list(self.data.keys())

            def get_collection_count(self, collection: str) -> int:
                return len(self.data.get(collection, {}))

        store = SimpleVectorStore()
        store.add_documents("test_col", ["doc1", "doc2"], ["id1", "id2"])
        assert "test_col" in store.list_collections()
        assert store.get_collection_count("test_col") == 2
