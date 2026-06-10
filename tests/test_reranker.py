#!/usr/bin/env python3
"""Reranker 模块测试

覆盖：
- CrossEncoderReranker：mock 模型推理，验证排序和分数归一化
- IdentityReranker：不做重排序
- create_reranker() 工厂：provider 选择和参数传递
- rerank_candidates() 集成：Settings 控制启用/禁用
"""

from unittest import TestCase
from unittest.mock import MagicMock, patch

from dochris.rag.reranker.cross_encoder import CrossEncoderReranker
from dochris.rag.schemas import RetrievalCandidate


def _make_candidate(
    idx: int = 0,
    text: str = "测试文本",
    source: str = "test.md",
    channel: str = "concept",
    score: float = 0.5,
    manifest_id: str | None = None,
) -> RetrievalCandidate:
    """构建测试用 RetrievalCandidate"""
    return RetrievalCandidate(
        id=f"test_{idx}",
        text=text,
        source=source,
        channel=channel,
        retriever="keyword_concept",
        raw_score=score * 10,
        score_kind="keyword",
        normalized_score=score,
        rank=idx + 1,
        channel_rank=idx + 1,
        manifest_id=manifest_id or f"SRC-{idx:04d}",
        metadata={"title": f"文档 {idx}"},
    )


class TestCrossEncoderReranker(TestCase):
    """CrossEncoderReranker 测试（mock 模型）"""

    @patch("dochris.rag.reranker.cross_encoder.CrossEncoderReranker._ensure_model")
    def test_rerank_sorts_by_score(self, mock_ensure: MagicMock) -> None:
        """rerank 按分数降序排序"""
        # Mock predict 返回逆序分数
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.1, 0.9, 0.5]

        reranker = CrossEncoderReranker()
        reranker._model = mock_model

        candidates = [
            _make_candidate(0, text="低相关"),
            _make_candidate(1, text="高相关"),
            _make_candidate(2, text="中相关"),
        ]

        result = reranker.rerank("测试查询", candidates, top_k=3)

        self.assertEqual(len(result), 3)
        # 最高分排第一
        self.assertEqual(result[0].text, "高相关")
        self.assertEqual(result[1].text, "中相关")
        self.assertEqual(result[2].text, "低相关")

    @patch("dochris.rag.reranker.cross_encoder.CrossEncoderReranker._ensure_model")
    def test_rerank_respects_top_k(self, mock_ensure: MagicMock) -> None:
        """rerank 截断到 top_k"""
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.9, 0.1, 0.5, 0.8, 0.3]

        reranker = CrossEncoderReranker()
        reranker._model = mock_model

        candidates = [_make_candidate(i) for i in range(5)]
        result = reranker.rerank("测试", candidates, top_k=2)

        self.assertEqual(len(result), 2)

    @patch("dochris.rag.reranker.cross_encoder.CrossEncoderReranker._ensure_model")
    def test_rerank_fills_rerank_score(self, mock_ensure: MagicMock) -> None:
        """rerank 结果包含 rerank_score 字段"""
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.8, 0.2]

        reranker = CrossEncoderReranker()
        reranker._model = mock_model

        candidates = [_make_candidate(0), _make_candidate(1)]
        result = reranker.rerank("测试", candidates, top_k=2)

        for c in result:
            self.assertIsNotNone(c.rerank_score)
            self.assertGreaterEqual(c.rerank_score, 0.0)
            self.assertLessEqual(c.rerank_score, 1.0)

    @patch("dochris.rag.reranker.cross_encoder.CrossEncoderReranker._ensure_model")
    def test_rerank_updates_score_kind(self, mock_ensure: MagicMock) -> None:
        """rerank 后 score_kind 变为 'rerank'"""
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.5]

        reranker = CrossEncoderReranker()
        reranker._model = mock_model

        candidates = [_make_candidate(0)]
        result = reranker.rerank("测试", candidates, top_k=1)

        self.assertEqual(result[0].score_kind, "rerank")

    def test_rerank_empty_candidates(self) -> None:
        """空候选列表返回空"""
        reranker = CrossEncoderReranker()
        result = reranker.rerank("测试", [], top_k=5)
        self.assertEqual(result, [])


class TestIdentityReranker(TestCase):
    """IdentityReranker 测试"""

    def test_returns_first_top_k(self) -> None:
        """直接返回前 top_k 候选"""
        from dochris.rag.reranker.cross_encoder import IdentityReranker

        candidates = [_make_candidate(i) for i in range(5)]
        reranker = IdentityReranker()

        result = reranker.rerank("测试", candidates, top_k=3)

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].id, "test_0")
        self.assertEqual(result[1].id, "test_1")
        self.assertEqual(result[2].id, "test_2")

    def test_preserves_original_scores(self) -> None:
        """不修改任何分数"""
        from dochris.rag.reranker.cross_encoder import IdentityReranker

        candidates = [_make_candidate(0, score=0.8)]
        reranker = IdentityReranker()

        result = reranker.rerank("测试", candidates, top_k=1)

        self.assertIsNone(result[0].rerank_score)
        self.assertEqual(result[0].normalized_score, 0.8)


class TestRerankerFactory(TestCase):
    """create_reranker() 工厂测试"""

    def test_create_bge_provider(self) -> None:
        """bge provider 创建 CrossEncoderReranker"""
        from dochris.rag.reranker.cross_encoder import CrossEncoderReranker
        from dochris.rag.reranker.factory import create_reranker

        reranker = create_reranker("bge")
        self.assertIsInstance(reranker, CrossEncoderReranker)
        self.assertEqual(reranker._model_name, "BAAI/bge-reranker-base")

    def test_create_identity_provider(self) -> None:
        """identity provider 创建 IdentityReranker"""
        from dochris.rag.reranker.cross_encoder import IdentityReranker
        from dochris.rag.reranker.factory import create_reranker

        reranker = create_reranker("identity")
        self.assertIsInstance(reranker, IdentityReranker)

    def test_create_unknown_provider_raises(self) -> None:
        """未知 provider 抛出 ValueError"""
        from dochris.rag.reranker.factory import create_reranker

        with self.assertRaises(ValueError) as ctx:
            create_reranker("nonexistent")
        self.assertIn("nonexistent", str(ctx.exception))

    def test_custom_model_name(self) -> None:
        """自定义模型名透传"""
        from dochris.rag.reranker.factory import create_reranker

        reranker = create_reranker("bge", model_name="custom-model")
        self.assertEqual(reranker._model_name, "custom-model")


class TestRerankCandidatesIntegration(TestCase):
    """rerank_candidates() 与 Settings 集成测试"""

    @patch("dochris.phases.query_engine.get_settings")
    def test_rerank_disabled_returns_truncated(self, mock_settings: MagicMock) -> None:
        """reranker_enabled='false' 时直接截断"""
        from dochris.phases.query_engine import rerank_candidates

        settings = MagicMock()
        settings.reranker_enabled = "false"
        mock_settings.return_value = settings

        candidates = [_make_candidate(i) for i in range(10)]
        result = rerank_candidates("测试", candidates, top_k=3)

        self.assertEqual(len(result), 3)
        # 不经过 reranker，保持原始对象
        self.assertIsNone(result[0].rerank_score)

    @patch("dochris.rag.reranker.factory.create_reranker")
    @patch("dochris.phases.query_engine.get_settings")
    def test_rerank_enabled_calls_reranker(self, mock_settings: MagicMock, mock_factory: MagicMock) -> None:
        """reranker_enabled='true' 时调用 create_reranker"""
        from dochris.phases.query_engine import rerank_candidates

        settings = MagicMock()
        settings.reranker_enabled = "true"
        settings.reranker_provider = "identity"
        settings.reranker_model = "test-model"
        mock_settings.return_value = settings

        # mock reranker 返回前 2 个
        mock_reranker = MagicMock()
        mock_reranker.rerank.return_value = [_make_candidate(0), _make_candidate(1)]
        mock_factory.return_value = mock_reranker

        candidates = [_make_candidate(i) for i in range(5)]
        result = rerank_candidates("测试", candidates, top_k=2)

        self.assertEqual(len(result), 2)
        mock_factory.assert_called_once_with(
            provider="identity", model_name="test-model"
        )
        mock_reranker.rerank.assert_called_once()

    def test_rerank_empty_candidates(self) -> None:
        """空候选列表"""
        from dochris.phases.query_engine import rerank_candidates

        with patch("dochris.phases.query_engine.get_settings") as mock_s:
            mock_s.return_value = MagicMock(reranker_enabled="false")
            result = rerank_candidates("测试", [], top_k=5)

        self.assertEqual(result, [])

    @patch("dochris.rag.reranker.factory.create_reranker")
    @patch("dochris.phases.query_engine.get_settings")
    def test_rerank_import_error_fallback(self, mock_settings: MagicMock, mock_factory: MagicMock) -> None:
        """依赖缺失时回退到截断"""
        from dochris.phases.query_engine import rerank_candidates

        settings = MagicMock()
        settings.reranker_enabled = "true"
        settings.reranker_provider = "bge"
        settings.reranker_model = "test"
        mock_settings.return_value = settings
        mock_factory.side_effect = ImportError("sentence-transformers not found")

        candidates = [_make_candidate(i) for i in range(5)]
        result = rerank_candidates("测试", candidates, top_k=3)

        # 回退：直接截断，不报错
        self.assertEqual(len(result), 3)
