"""CohereReranker 测试（mock HTTP 层，不发真实请求）。

覆盖 RAG-08 收敛：settings 声明的 cohere provider 必须由 factory 真实支持。
"""

from unittest import TestCase
from unittest.mock import patch

from dochris.rag.reranker.cohere import CohereReranker
from dochris.rag.reranker.factory import create_reranker
from tests.test_reranker import _make_candidate


class TestCohereFactory(TestCase):
    """factory 对 cohere provider 的支持。"""

    def test_cohere_registered_in_factory(self) -> None:
        """cohere 必须是 factory 的合法 provider（RAG-08）。"""
        with patch.dict("os.environ", {"COHERE_API_KEY": "test-key"}):
            reranker = create_reranker("cohere", model_name="rerank-v3.5")
        self.assertIsInstance(reranker, CohereReranker)
        self.assertEqual(reranker.model_name, "rerank-v3.5")

    def test_cohere_without_key_raises_value_error(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError):
                create_reranker("cohere")

    def test_cohere_rejects_cross_encoder_model_name(self) -> None:
        """BGE 模型名传入 cohere 时回落到 Cohere 默认模型。"""
        with patch.dict("os.environ", {"COHERE_API_KEY": "test-key"}):
            reranker = create_reranker("cohere", model_name="BAAI/bge-reranker-base")
        self.assertEqual(reranker.model_name, "rerank-multilingual-v3.0")


class TestCohereReranker(TestCase):
    """CohereReranker 行为（mock _rerank_response）。"""

    def test_requires_api_key(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError):
                CohereReranker()

    def test_rerank_sorts_and_truncates(self) -> None:
        reranker = CohereReranker(api_key="test-key")
        candidates = [
            _make_candidate(0, text="低相关"),
            _make_candidate(1, text="高相关"),
            _make_candidate(2, text="中相关"),
        ]
        # Cohere 返回的 index 顺序即为相关性顺序
        with patch.object(
            reranker,
            "_rerank_response",
            return_value=[
                {"index": 1, "relevance_score": 0.98},
                {"index": 2, "relevance_score": 0.55},
                {"index": 0, "relevance_score": 0.10},
            ],
        ):
            reranked = reranker.rerank("查询", candidates, top_k=2)

        self.assertEqual([c.id for c in reranked], ["test_1", "test_2"])
        self.assertEqual(reranked[0].rerank_score, 0.98)
        self.assertEqual(reranked[0].normalized_score, 0.98)

    def test_rerank_empty_candidates(self) -> None:
        reranker = CohereReranker(api_key="test-key")
        self.assertEqual(reranker.rerank("查询", [], top_k=5), [])

    def test_rerank_clamps_scores(self) -> None:
        reranker = CohereReranker(api_key="test-key")
        candidates = [_make_candidate(0, text="x"), _make_candidate(1, text="y")]
        with patch.object(
            reranker,
            "_rerank_response",
            return_value=[
                {"index": 0, "relevance_score": 1.7},
                {"index": 1, "relevance_score": -0.5},
            ],
        ):
            reranked = reranker.rerank("查询", candidates, top_k=5)

        self.assertEqual(reranked[0].normalized_score, 1.0)
        self.assertEqual(reranked[1].normalized_score, 0.0)


class TestFaissEmbeddingDefault(TestCase):
    """FAISS 默认 embedding 与 ChromaDB/settings 一致（RAG-09）。"""

    def test_faiss_default_uses_settings_embedding(self) -> None:
        from dochris.vector.faiss_store import FAISSStore

        with patch("dochris.settings.get_settings") as mock_settings:
            mock_settings.return_value.embedding_model = "BAAI/bge-small-zh-v1.5"
            store = FAISSStore()
        self.assertEqual(store._embedding_model_name, "BAAI/bge-small-zh-v1.5")

    def test_faiss_explicit_model_wins(self) -> None:
        from dochris.vector.faiss_store import FAISSStore

        store = FAISSStore(embedding_model="custom-model")
        self.assertEqual(store._embedding_model_name, "custom-model")
