#!/usr/bin/env python3
"""测试 RAG 统一数据模型与检索候选转换

覆盖：
- RetrievalCandidate 数据类字段与 content_hash()
- SourceRef 数据类
- normalize_keyword_score / normalize_vector_score / normalize_score 归一化函数
- retrieve_candidates() 核心逻辑：三通道转换、归一化排序、去重、candidate_k 截断
"""

import hashlib
import unittest
from unittest.mock import Mock, patch

from dochris.rag.schemas import (
    RetrievalCandidate,
    SourceRef,
    normalize_keyword_score,
    normalize_score,
    normalize_vector_score,
)

# ============================================================
# 归一化函数测试
# ============================================================


class TestNormalizeKeywordScore(unittest.TestCase):
    """测试关键词分数归一化"""

    def test_zero_score(self) -> None:
        """分数为 0 时返回 0.0"""
        self.assertEqual(normalize_keyword_score(0), 0.0)

    def test_negative_score(self) -> None:
        """负分数返回 0.0"""
        self.assertEqual(normalize_keyword_score(-5), 0.0)

    def test_low_score(self) -> None:
        """低分（score=5）映射到约 0.63"""
        result = normalize_keyword_score(5)
        self.assertAlmostEqual(result, 0.632, places=2)

    def test_medium_score(self) -> None:
        """中等分数（score=10）映射到约 0.86"""
        result = normalize_keyword_score(10)
        self.assertAlmostEqual(result, 0.865, places=2)

    def test_high_score(self) -> None:
        """高分（score=15）映射到约 0.95"""
        result = normalize_keyword_score(15)
        self.assertAlmostEqual(result, 0.950, places=2)

    def test_very_high_score(self) -> None:
        """极高分数（score=100）不超过 1.0"""
        result = normalize_keyword_score(100)
        self.assertLessEqual(result, 1.0)
        self.assertGreater(result, 0.99)

    def test_monotonically_increasing(self) -> None:
        """分数越高归一化值越大（单调递增）"""
        results = [normalize_keyword_score(s) for s in range(0, 30)]
        for i in range(1, len(results)):
            self.assertGreaterEqual(results[i], results[i - 1])


class TestNormalizeVectorScore(unittest.TestCase):
    """测试向量距离归一化"""

    def test_zero_distance(self) -> None:
        """距离为 0 时返回 1.0（完全匹配）"""
        result = normalize_vector_score(0)
        self.assertAlmostEqual(result, 1.0, places=2)

    def test_negative_distance(self) -> None:
        """负距离（异常值）返回 0.0（让错误数据沉底，而非获最高分污染结果）"""
        result = normalize_vector_score(-0.5)
        self.assertEqual(result, 0.0)

    def test_small_distance(self) -> None:
        """小距离（d=0.1）映射到约 0.91"""
        result = normalize_vector_score(0.1)
        self.assertAlmostEqual(result, 0.909, places=2)

    def test_medium_distance(self) -> None:
        """中等距离（d=0.5）映射到约 0.67"""
        result = normalize_vector_score(0.5)
        self.assertAlmostEqual(result, 0.667, places=2)

    def test_large_distance(self) -> None:
        """大距离（d=2.0）映射到约 0.33"""
        result = normalize_vector_score(2.0)
        self.assertAlmostEqual(result, 0.333, places=2)

    def test_monotonically_decreasing(self) -> None:
        """距离越大归一化值越小（单调递减）"""
        results = [normalize_vector_score(d) for d in [0, 0.1, 0.5, 1.0, 2.0, 5.0]]
        for i in range(1, len(results)):
            self.assertLessEqual(results[i], results[i - 1])


class TestNormalizeScore(unittest.TestCase):
    """测试统一归一化入口"""

    def test_keyword_dispatch(self) -> None:
        """score_kind=keyword 分发到 normalize_keyword_score"""
        result = normalize_score(10, "keyword")
        self.assertEqual(result, normalize_keyword_score(10))

    def test_cosine_distance_dispatch(self) -> None:
        """score_kind=cosine_distance 分发到 normalize_vector_score"""
        result = normalize_score(0, "cosine_distance", raw_distance=0.5)
        self.assertEqual(result, normalize_vector_score(0.5))

    def test_l2_distance_dispatch(self) -> None:
        """score_kind=l2_distance 分发到 normalize_vector_score"""
        result = normalize_score(0, "l2_distance", raw_distance=2.0)
        self.assertEqual(result, normalize_vector_score(2.0))

    def test_l2_distance_without_raw_distance(self) -> None:
        """score_kind=l2_distance 但无 raw_distance 时回退到 raw_score"""
        result = normalize_score(1.0, "l2_distance", raw_distance=None)
        self.assertEqual(result, normalize_vector_score(1.0))

    def test_rerank_within_range(self) -> None:
        """rerank score 在 [0, 1] 内直接保留"""
        self.assertEqual(normalize_score(0.85, "rerank"), 0.85)
        self.assertEqual(normalize_score(0.0, "rerank"), 0.0)
        self.assertEqual(normalize_score(1.0, "rerank"), 1.0)

    def test_rerank_clamp(self) -> None:
        """rerank score 超出 [0, 1] 时裁剪"""
        self.assertEqual(normalize_score(1.5, "rerank"), 1.0)
        self.assertEqual(normalize_score(-0.1, "rerank"), 0.0)


# ============================================================
# RetrievalCandidate 数据类测试
# ============================================================


class TestRetrievalCandidate(unittest.TestCase):
    """测试 RetrievalCandidate 数据类"""

    def _make_candidate(self, **overrides) -> RetrievalCandidate:
        """创建测试用候选"""
        defaults = {
            "id": "concept_SRC-0001_0",
            "text": "这是一段测试文本内容",
            "source": "wiki",
            "channel": "concept",
            "retriever": "keyword_concept",
            "raw_score": 10.0,
            "score_kind": "keyword",
            "normalized_score": 0.865,
        }
        defaults.update(overrides)
        return RetrievalCandidate(**defaults)

    def test_content_hash_deterministic(self) -> None:
        """相同文本产生相同 hash"""
        c1 = self._make_candidate(text="完全相同的文本")
        c2 = self._make_candidate(id="other_1", text="完全相同的文本")
        self.assertEqual(c1.content_hash(), c2.content_hash())

    def test_content_hash_differs_for_different_text(self) -> None:
        """不同文本产生不同 hash"""
        c1 = self._make_candidate(text="第一段文本")
        c2 = self._make_candidate(id="other_1", text="第二段文本")
        self.assertNotEqual(c1.content_hash(), c2.content_hash())

    def test_content_hash_matches_md5(self) -> None:
        """content_hash 使用 MD5 前 12 字符"""
        c = self._make_candidate(text="测试文本")
        expected = hashlib.md5("测试文本".encode()).hexdigest()[:12]
        self.assertEqual(c.content_hash(), expected)

    def test_all_channels(self) -> None:
        """所有 channel 类型都可以创建"""
        for channel in ("concept", "summary", "vector", "chunk"):
            c = self._make_candidate(channel=channel)
            self.assertEqual(c.channel, channel)

    def test_all_score_kinds(self) -> None:
        """所有 score_kind 类型都可以创建"""
        for kind in ("keyword", "cosine_distance", "l2_distance", "rerank"):
            c = self._make_candidate(score_kind=kind)
            self.assertEqual(c.score_kind, kind)

    def test_default_fields(self) -> None:
        """可选字段有正确默认值"""
        c = self._make_candidate()
        self.assertIsNone(c.raw_distance)
        self.assertIsNone(c.rank)
        self.assertIsNone(c.channel_rank)
        self.assertIsNone(c.manifest_id)
        self.assertEqual(c.metadata, {})
        self.assertIsNone(c.rerank_score)

    def test_mutable_metadata_not_shared(self) -> None:
        """metadata 默认值不共享（dataclass field default_factory 正确）"""
        c1 = self._make_candidate()
        c2 = self._make_candidate()
        c1.metadata["key"] = "value"
        self.assertNotIn("key", c2.metadata)

    def test_rank_mutable(self) -> None:
        """rank 字段可修改（非 frozen dataclass）"""
        c = self._make_candidate()
        self.assertIsNone(c.rank)
        c.rank = 1
        self.assertEqual(c.rank, 1)


class TestSourceRef(unittest.TestCase):
    """测试 SourceRef 数据类"""

    def test_frozen(self) -> None:
        """SourceRef 是不可变的"""
        ref = SourceRef(
            manifest_id="SRC-0001",
            source="test.md",
            channel="concept",
            text_hash="abc123def456",
            score=10.0,
        )
        with self.assertRaises(AttributeError):
            ref.score = 5.0  # type: ignore[misc]

    def test_fields(self) -> None:
        """字段正确赋值"""
        ref = SourceRef(
            manifest_id="SRC-0001",
            source="test.md",
            channel="vector",
            text_hash="abc123def456",
            score=0.85,
        )
        self.assertEqual(ref.manifest_id, "SRC-0001")
        self.assertEqual(ref.source, "test.md")
        self.assertEqual(ref.channel, "vector")
        self.assertEqual(ref.text_hash, "abc123def456")
        self.assertEqual(ref.score, 0.85)


# ============================================================
# retrieve_candidates() 集成测试
# ============================================================


class TestRetrieveCandidates(unittest.TestCase):
    """测试 retrieve_candidates() 函数"""

    def setUp(self) -> None:
        """清理 query_engine 缓存"""
        import dochris.phases.query_engine as qe

        qe._vector_store_cache = None
        qe._chromadb_client_cache = None
        qe._llm_client_cache = None

    def tearDown(self) -> None:
        """清理缓存"""
        import dochris.phases.query_engine as qe

        qe._vector_store_cache = None
        qe._chromadb_client_cache = None
        qe._llm_client_cache = None

    @patch("dochris.phases.query_engine.vector_search")
    @patch("dochris.phases.query_engine.search_summaries")
    @patch("dochris.phases.query_engine.search_concepts")
    @patch("dochris.phases.query_engine.get_settings")
    def test_returns_typed_candidates(
        self, mock_settings, mock_concepts, mock_summaries, mock_vector
    ) -> None:
        """返回 list[RetrievalCandidate] 而非 list[dict]"""
        mock_config = Mock()
        mock_config.vector_store = "chromadb"
        mock_settings.return_value = mock_config

        mock_concepts.return_value = [
            {
                "name": "概念1",
                "definition": "定义1",
                "score": 10,
                "source": "wiki",
                "manifest_id": "SRC-0001",
            }
        ]
        mock_summaries.return_value = []
        mock_vector.return_value = []

        from dochris.phases.query_engine import retrieve_candidates

        results = retrieve_candidates("测试", top_k=5)

        # 核心断言：返回的是 RetrievalCandidate 实例，不是 dict
        self.assertIsInstance(results, list)
        if results:
            self.assertIsInstance(results[0], RetrievalCandidate)
            self.assertNotIsInstance(results[0], dict)

    @patch("dochris.phases.query_engine.vector_search")
    @patch("dochris.phases.query_engine.search_summaries")
    @patch("dochris.phases.query_engine.search_concepts")
    @patch("dochris.phases.query_engine.get_settings")
    def test_concept_channel_fields(
        self, mock_settings, mock_concepts, mock_summaries, mock_vector
    ) -> None:
        """concept 通道候选字段正确"""
        mock_config = Mock()
        mock_config.vector_store = "chromadb"
        mock_settings.return_value = mock_config

        mock_concepts.return_value = [
            {
                "name": "机器学习",
                "definition": "机器学习是AI的子领域",
                "score": 15,
                "source": "wiki",
                "manifest_id": "SRC-0001",
                "title": "机器学习",
            }
        ]
        mock_summaries.return_value = []
        mock_vector.return_value = []

        from dochris.phases.query_engine import retrieve_candidates

        results = retrieve_candidates("机器学习", top_k=5)

        self.assertEqual(len(results), 1)
        c = results[0]
        self.assertEqual(c.channel, "concept")
        self.assertEqual(c.retriever, "keyword_concept")
        self.assertEqual(c.score_kind, "keyword")
        self.assertEqual(c.raw_score, 15.0)
        self.assertEqual(c.channel_rank, 1)
        self.assertEqual(c.manifest_id, "SRC-0001")
        self.assertIn("机器学习", c.metadata.get("name", ""))

    @patch("dochris.phases.query_engine.vector_search")
    @patch("dochris.phases.query_engine.search_summaries")
    @patch("dochris.phases.query_engine.search_concepts")
    @patch("dochris.phases.query_engine.get_settings")
    def test_summary_channel_fields(
        self, mock_settings, mock_concepts, mock_summaries, mock_vector
    ) -> None:
        """summary 通道候选字段正确"""
        mock_config = Mock()
        mock_config.vector_store = "chromadb"
        mock_settings.return_value = mock_config

        mock_concepts.return_value = []
        mock_summaries.return_value = [
            {
                "title": "深度学习入门",
                "content": "深度学习是机器学习的子领域",
                "score": 8,
                "source": "outputs",
                "manifest_id": "SRC-0002",
            }
        ]
        mock_vector.return_value = []

        from dochris.phases.query_engine import retrieve_candidates

        results = retrieve_candidates("深度学习", top_k=5)

        self.assertEqual(len(results), 1)
        c = results[0]
        self.assertEqual(c.channel, "summary")
        self.assertEqual(c.retriever, "keyword_summary")
        self.assertEqual(c.channel_rank, 1)

    @patch("dochris.phases.query_engine.vector_search")
    @patch("dochris.phases.query_engine.search_summaries")
    @patch("dochris.phases.query_engine.search_concepts")
    @patch("dochris.phases.query_engine.get_settings")
    def test_vector_channel_chromadb(
        self, mock_settings, mock_concepts, mock_summaries, mock_vector
    ) -> None:
        """vector 通道 ChromaDB 使用 cosine_distance 归一化"""
        mock_config = Mock()
        mock_config.vector_store = "chromadb"
        mock_settings.return_value = mock_config

        mock_concepts.return_value = []
        mock_summaries.return_value = []
        mock_vector.return_value = [
            {"text": "向量内容", "score": 0.3, "source": "test.md", "manifest_id": None}
        ]

        from dochris.phases.query_engine import retrieve_candidates

        results = retrieve_candidates("测试", top_k=5)

        self.assertEqual(len(results), 1)
        c = results[0]
        self.assertEqual(c.channel, "vector")
        self.assertEqual(c.retriever, "chromadb")
        self.assertEqual(c.score_kind, "cosine_distance")
        self.assertEqual(c.raw_score, 0.3)
        self.assertEqual(c.raw_distance, 0.3)
        self.assertAlmostEqual(c.normalized_score, normalize_vector_score(0.3))

    @patch("dochris.phases.query_engine.vector_search")
    @patch("dochris.phases.query_engine.search_summaries")
    @patch("dochris.phases.query_engine.search_concepts")
    @patch("dochris.phases.query_engine.get_settings")
    def test_vector_channel_faiss(
        self, mock_settings, mock_concepts, mock_summaries, mock_vector
    ) -> None:
        """vector 通道 FAISS 使用 l2_distance 归一化"""
        mock_config = Mock()
        mock_config.vector_store = "faiss"
        mock_settings.return_value = mock_config

        mock_concepts.return_value = []
        mock_summaries.return_value = []
        mock_vector.return_value = [
            {"text": "向量内容", "score": 1.5, "source": "test.md", "manifest_id": None}
        ]

        from dochris.phases.query_engine import retrieve_candidates

        results = retrieve_candidates("测试", top_k=5)

        self.assertEqual(len(results), 1)
        c = results[0]
        self.assertEqual(c.score_kind, "l2_distance")
        self.assertEqual(c.retriever, "faiss")

    @patch("dochris.phases.query_engine.vector_search")
    @patch("dochris.phases.query_engine.search_summaries")
    @patch("dochris.phases.query_engine.search_concepts")
    @patch("dochris.phases.query_engine.get_settings")
    def test_sorted_by_normalized_score(
        self, mock_settings, mock_concepts, mock_summaries, mock_vector
    ) -> None:
        """结果按 normalized_score 降序排列"""
        mock_config = Mock()
        mock_config.vector_store = "chromadb"
        mock_settings.return_value = mock_config

        mock_concepts.return_value = [
            {
                "name": "低分概念",
                "definition": "内容",
                "score": 3,
                "source": "wiki",
                "manifest_id": "SRC-0001",
            }
        ]
        mock_summaries.return_value = [
            {
                "title": "高分摘要",
                "content": "内容",
                "score": 20,
                "source": "wiki",
                "manifest_id": "SRC-0002",
            }
        ]
        mock_vector.return_value = []

        from dochris.phases.query_engine import retrieve_candidates

        results = retrieve_candidates("测试", top_k=5)

        # 摘要 (score=20) 的归一化分应高于概念 (score=3)
        self.assertEqual(len(results), 2)
        self.assertGreater(results[0].normalized_score, results[1].normalized_score)

    @patch("dochris.phases.query_engine.vector_search")
    @patch("dochris.phases.query_engine.search_summaries")
    @patch("dochris.phases.query_engine.search_concepts")
    @patch("dochris.phases.query_engine.get_settings")
    def test_dedup_by_manifest_and_content_hash(
        self, mock_settings, mock_concepts, mock_summaries, mock_vector
    ) -> None:
        """去重：同一 manifest_id + 同一内容 hash 只保留最高分"""
        mock_config = Mock()
        mock_config.vector_store = "chromadb"
        mock_settings.return_value = mock_config

        # 同一 manifest_id + 相同内容 → 应去重
        mock_concepts.return_value = [
            {
                "name": "概念A",
                "definition": "相同内容",
                "score": 5,
                "source": "wiki",
                "manifest_id": "SRC-0001",
            }
        ]
        mock_summaries.return_value = [
            {
                "title": "摘要A",
                "content": "相同内容",
                "score": 15,
                "source": "wiki",
                "manifest_id": "SRC-0001",
            }
        ]
        mock_vector.return_value = []

        from dochris.phases.query_engine import retrieve_candidates

        results = retrieve_candidates("测试", top_k=5)

        # 只保留高分的一个
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].raw_score, 15.0)

    @patch("dochris.phases.query_engine.vector_search")
    @patch("dochris.phases.query_engine.search_summaries")
    @patch("dochris.phases.query_engine.search_concepts")
    @patch("dochris.phases.query_engine.get_settings")
    def test_no_dedup_different_manifest(
        self, mock_settings, mock_concepts, mock_summaries, mock_vector
    ) -> None:
        """不同 manifest_id 的相同内容不去重"""
        mock_config = Mock()
        mock_config.vector_store = "chromadb"
        mock_settings.return_value = mock_config

        mock_concepts.return_value = [
            {
                "name": "概念A",
                "definition": "相同内容",
                "score": 5,
                "source": "wiki",
                "manifest_id": "SRC-0001",
            }
        ]
        mock_summaries.return_value = [
            {
                "title": "摘要B",
                "content": "相同内容",
                "score": 10,
                "source": "wiki",
                "manifest_id": "SRC-0002",
            }
        ]
        mock_vector.return_value = []

        from dochris.phases.query_engine import retrieve_candidates

        results = retrieve_candidates("测试", top_k=5)

        self.assertEqual(len(results), 2)

    @patch("dochris.phases.query_engine.vector_search")
    @patch("dochris.phases.query_engine.search_summaries")
    @patch("dochris.phases.query_engine.search_concepts")
    @patch("dochris.phases.query_engine.get_settings")
    def test_candidate_k_truncation(
        self, mock_settings, mock_concepts, mock_summaries, mock_vector
    ) -> None:
        """candidate_k 截断生效"""
        mock_config = Mock()
        mock_config.vector_store = "chromadb"
        mock_settings.return_value = mock_config

        mock_concepts.return_value = [
            {
                "name": f"概念{i}",
                "definition": f"内容{i}",
                "score": 10 - i,
                "source": "wiki",
                "manifest_id": f"SRC-000{i}",
            }
            for i in range(5)
        ]
        mock_summaries.return_value = []
        mock_vector.return_value = []

        from dochris.phases.query_engine import retrieve_candidates

        results = retrieve_candidates("测试", top_k=10, candidate_k=3)
        self.assertEqual(len(results), 3)

    @patch("dochris.phases.query_engine.vector_search")
    @patch("dochris.phases.query_engine.search_summaries")
    @patch("dochris.phases.query_engine.search_concepts")
    @patch("dochris.phases.query_engine.get_settings")
    def test_global_rank_populated(
        self, mock_settings, mock_concepts, mock_summaries, mock_vector
    ) -> None:
        """全局 rank 在去重后正确填充"""
        mock_config = Mock()
        mock_config.vector_store = "chromadb"
        mock_settings.return_value = mock_config

        mock_concepts.return_value = [
            {
                "name": "A",
                "definition": "内容A",
                "score": 5,
                "source": "wiki",
                "manifest_id": "SRC-0001",
            },
            {
                "name": "B",
                "definition": "内容B",
                "score": 3,
                "source": "wiki",
                "manifest_id": "SRC-0002",
            },
        ]
        mock_summaries.return_value = []
        mock_vector.return_value = []

        from dochris.phases.query_engine import retrieve_candidates

        results = retrieve_candidates("测试", top_k=5)

        # 全局 rank 应从 1 开始递增
        ranks = [c.rank for c in results]
        self.assertEqual(ranks, list(range(1, len(results) + 1)))

    @patch("dochris.phases.query_engine.vector_search")
    @patch("dochris.phases.query_engine.search_summaries")
    @patch("dochris.phases.query_engine.search_concepts")
    @patch("dochris.phases.query_engine.get_settings")
    def test_channel_rank_preserved(
        self, mock_settings, mock_concepts, mock_summaries, mock_vector
    ) -> None:
        """通道内排名 (channel_rank) 不被全局 rank 覆盖"""
        mock_config = Mock()
        mock_config.vector_store = "chromadb"
        mock_settings.return_value = mock_config

        # 两个 concept 候选，channel_rank 分别为 1 和 2
        mock_concepts.return_value = [
            {
                "name": "概念1",
                "definition": "内容1",
                "score": 10,
                "source": "wiki",
                "manifest_id": "SRC-0001",
            },
            {
                "name": "概念2",
                "definition": "内容2",
                "score": 5,
                "source": "wiki",
                "manifest_id": "SRC-0002",
            },
        ]
        mock_summaries.return_value = []
        mock_vector.return_value = []

        from dochris.phases.query_engine import retrieve_candidates

        results = retrieve_candidates("测试", top_k=5)

        # 找到两个 concept 通道的候选
        concept_candidates = [c for c in results if c.channel == "concept"]
        self.assertEqual(len(concept_candidates), 2)

        # channel_rank 应保留通道内原始位置
        channel_ranks = sorted(c.channel_rank for c in concept_candidates)
        self.assertEqual(channel_ranks, [1, 2])

        # global rank 与 channel_rank 不同（全局排序后）
        for c in concept_candidates:
            self.assertIsNotNone(c.rank)
            self.assertIsNotNone(c.channel_rank)

    @patch("dochris.phases.query_engine.vector_search")
    @patch("dochris.phases.query_engine.search_summaries")
    @patch("dochris.phases.query_engine.search_concepts")
    @patch("dochris.phases.query_engine.get_settings")
    def test_empty_results(self, mock_settings, mock_concepts, mock_summaries, mock_vector) -> None:
        """所有通道都无结果时返回空列表"""
        mock_config = Mock()
        mock_config.vector_store = "chromadb"
        mock_settings.return_value = mock_config

        mock_concepts.return_value = []
        mock_summaries.return_value = []
        mock_vector.return_value = []

        from dochris.phases.query_engine import retrieve_candidates

        results = retrieve_candidates("不存在的查询", top_k=5)
        self.assertEqual(results, [])

    @patch("dochris.phases.query_engine.vector_search")
    @patch("dochris.phases.query_engine.search_summaries")
    @patch("dochris.phases.query_engine.search_concepts")
    @patch("dochris.phases.query_engine.get_settings")
    def test_uses_settings_not_env(
        self, mock_settings, mock_concepts, mock_summaries, mock_vector
    ) -> None:
        """vector_store 类型从 Settings 读取，不从 os.environ 读取"""
        mock_config = Mock()
        mock_config.vector_store = "faiss"
        mock_settings.return_value = mock_config

        mock_concepts.return_value = []
        mock_summaries.return_value = []
        mock_vector.return_value = [
            {"text": "内容", "score": 0.5, "source": "test.md", "manifest_id": None}
        ]

        from dochris.phases.query_engine import retrieve_candidates

        results = retrieve_candidates("测试", top_k=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].score_kind, "l2_distance")
        self.assertEqual(results[0].retriever, "faiss")


if __name__ == "__main__":
    unittest.main()
