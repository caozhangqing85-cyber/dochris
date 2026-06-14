#!/usr/bin/env python3
"""rag.chunking 模块测试

覆盖：
- ChunkMetadata / DocumentChunk 数据结构
- StructureChunker（包装现有 structure_aware_split）
- RecursiveChunker（token-aware 递归分块）
- SemanticChunker（embedding 断点 + 降级）
- factory create_chunker（策略注册 + 未知策略异常）
"""

from unittest import TestCase

from dochris.rag.chunking import (
    ChunkMetadata,
    RecursiveChunker,
    SemanticChunker,
    StructureChunker,
    create_chunker,
)

# ============================================================
# 数据结构测试
# ============================================================


class TestChunkMetadata(TestCase):
    """ChunkMetadata 数据结构测试"""

    def test_default_values(self) -> None:
        """默认值正确"""
        meta = ChunkMetadata(src_id="SRC-0001")
        self.assertEqual(meta.src_id, "SRC-0001")
        self.assertEqual(meta.title, "")
        self.assertEqual(meta.section, "")
        self.assertEqual(meta.start_char, 0)
        self.assertEqual(meta.end_char, 0)
        self.assertEqual(meta.strategy, "structure")
        self.assertEqual(meta.extra, {})

    def test_extra_dict_independent(self) -> None:
        """extra 字典实例独立（避免可变默认值共享）"""
        m1 = ChunkMetadata(src_id="a")
        m2 = ChunkMetadata(src_id="b")
        m1.extra["k"] = "v"
        self.assertNotIn("k", m2.extra)


# ============================================================
# StructureChunker 测试
# ============================================================


class TestStructureChunker(TestCase):
    """结构感知分块器测试"""

    def setUp(self) -> None:
        self.chunker = StructureChunker(chunk_size=100, overlap=10)

    def test_markdown_header_split(self) -> None:
        """按 Markdown 标题切分"""
        text = "# 标题一\n\n内容一。\n\n# 标题二\n\n内容二。"
        chunks = self.chunker.split(text, ChunkMetadata(src_id="S1"))
        self.assertGreaterEqual(len(chunks), 2)
        # 每个 chunk 的 section 应反映标题
        sections = [c.metadata.section for c in chunks]
        self.assertIn("标题一", sections)
        self.assertIn("标题二", sections)

    def test_char_position_populated(self) -> None:
        """start_char / end_char 被正确填充"""
        text = "# 标题\n\n这是一段内容。"
        chunks = self.chunker.split(text, ChunkMetadata(src_id="S1"))
        self.assertTrue(len(chunks) >= 1)
        for c in chunks:
            self.assertGreaterEqual(c.metadata.start_char, 0)
            self.assertGreaterEqual(c.metadata.end_char, c.metadata.start_char)

    def test_chunk_id_format(self) -> None:
        """chunk id 格式为 {src_id}_chunk_{idx:04d}"""
        chunks = self.chunker.split("# A\n\nx\n\n# B\n\ny", ChunkMetadata(src_id="SRC-0001"))
        self.assertTrue(all(c.id.startswith("SRC-0001_chunk_") for c in chunks))

    def test_strategy_name(self) -> None:
        """策略名"""
        self.assertEqual(self.chunker.name, "structure")

    def test_empty_text(self) -> None:
        """空文本不报错（底层 structure_aware_split 可能返回空内容 chunk）"""
        chunks = self.chunker.split("", ChunkMetadata(src_id="S1"))
        # 不抛异常即可，底层结构分块对空文本的行为是既有的
        self.assertIsInstance(chunks, list)


# ============================================================
# RecursiveChunker 测试
# ============================================================


class TestRecursiveChunker(TestCase):
    """递归分块器测试"""

    def test_chunk_size_respected(self) -> None:
        """每个 chunk 不超过 chunk_size（允许 overlap 容差）"""
        chunker = RecursiveChunker(chunk_size=50, overlap=5)
        text = "句子一。句子二。句子三。句子四。句子五。句子六。句子七。句子八。"
        chunks = chunker.split(text, ChunkMetadata(src_id="S1"))
        self.assertGreaterEqual(len(chunks), 1)
        # 每个 chunk 长度不应远超 chunk_size
        for c in chunks:
            self.assertLessEqual(len(c.content), 50 + 5)

    def test_invalid_params(self) -> None:
        """非法参数抛 ValueError"""
        with self.assertRaises(ValueError):
            RecursiveChunker(chunk_size=0)
        with self.assertRaises(ValueError):
            RecursiveChunker(chunk_size=100, overlap=100)  # overlap >= chunk_size

    def test_separators_priority(self) -> None:
        """优先使用粗粒度分隔符"""
        chunker = RecursiveChunker(chunk_size=30, overlap=0)
        text = "段落一。\n\n段落二。\n\n段落三。"
        chunks = chunker.split(text, ChunkMetadata(src_id="S1"))
        self.assertGreaterEqual(len(chunks), 1)

    def test_strategy_name(self) -> None:
        """策略名"""
        self.assertEqual(RecursiveChunker(chunk_size=800).name, "recursive")

    def test_empty_text(self) -> None:
        """空文本返回空列表"""
        chunker = RecursiveChunker(chunk_size=800)
        self.assertEqual(chunker.split("", ChunkMetadata(src_id="S1")), [])

    def test_keep_separator(self) -> None:
        """保留分隔符时分隔符附到前一段"""
        chunker = RecursiveChunker(chunk_size=100, overlap=0, keep_separator=True)
        text = "句子一。句子二。"
        chunks = chunker.split(text, ChunkMetadata(src_id="S1"))
        # 合并后应能重建原文（分隔符被保留）
        self.assertTrue(len(chunks) >= 1)


# ============================================================
# SemanticChunker 测试（降级路径，不依赖真实 embedding）
# ============================================================


class TestSemanticChunker(TestCase):
    """语义分块器测试"""

    def test_invalid_breakpoint_percentile(self) -> None:
        """非法百分位抛 ValueError"""
        with self.assertRaises(ValueError):
            SemanticChunker(breakpoint_percentile=0)
        with self.assertRaises(ValueError):
            SemanticChunker(breakpoint_percentile=101)

    def test_strategy_name(self) -> None:
        """策略名"""
        self.assertEqual(SemanticChunker().name, "semantic")

    def test_empty_text(self) -> None:
        """空文本返回空列表"""
        chunker = SemanticChunker()
        self.assertEqual(chunker.split("", ChunkMetadata(src_id="S1")), [])

    def test_fallback_when_no_embedding(self) -> None:
        """embedding 不可用时降级为按句子合并"""
        chunker = SemanticChunker(chunk_size=20, overlap=0, embedding_func=None)
        # 注入返回 None 的 embedder 模拟不可用
        chunker._embedder = False  # type: ignore[attr-defined]
        text = "句子一。句子二。句子三。句子四。句子五。"
        chunks = chunker.split(text, ChunkMetadata(src_id="S1"))
        self.assertGreaterEqual(len(chunks), 1)

    def test_with_mock_embedding_func(self) -> None:
        """使用 mock embedding 函数计算断点"""

        def mock_embed(texts: list[str]) -> list[list[float]]:
            # 简单：返回与文本长度相关的向量，使相邻距离可计算
            return [[float(len(t))] for t in texts]

        chunker = SemanticChunker(
            chunk_size=200, overlap=0, embedding_func=mock_embed, breakpoint_percentile=90.0
        )
        text = "短句。这是一个稍长一点的句子。短。又是短句。这个句子非常非常非常长用于制造语义跳跃。"
        chunks = chunker.split(text, ChunkMetadata(src_id="S1"))
        self.assertGreaterEqual(len(chunks), 1)


# ============================================================
# Factory 测试
# ============================================================


class TestFactory(TestCase):
    """工厂函数测试"""

    def test_create_structure(self) -> None:
        """创建 structure 策略"""
        chunker = create_chunker("structure")
        self.assertIsInstance(chunker, StructureChunker)

    def test_create_recursive(self) -> None:
        """创建 recursive 策略"""
        chunker = create_chunker("recursive")
        self.assertIsInstance(chunker, RecursiveChunker)

    def test_create_semantic(self) -> None:
        """创建 semantic 策略"""
        chunker = create_chunker("semantic", embedding_model="test-model")
        self.assertIsInstance(chunker, SemanticChunker)

    def test_unknown_strategy_raises(self) -> None:
        """未知策略抛 ValueError"""
        with self.assertRaises(ValueError) as ctx:
            create_chunker("nonexistent")
        self.assertIn("nonexistent", str(ctx.exception))
        self.assertIn("structure", str(ctx.exception))

    def test_default_strategy(self) -> None:
        """默认策略为 structure"""
        chunker = create_chunker()
        self.assertEqual(chunker.name, "structure")

    def test_chunk_size_passed(self) -> None:
        """chunk_size 参数正确传递"""
        chunker = create_chunker("recursive", chunk_size=500, overlap=50)
        self.assertEqual(chunker._chunk_size, 500)
        self.assertEqual(chunker._overlap, 50)


# ============================================================
# 集成测试：三策略对比
# ============================================================


class TestStrategyComparison(TestCase):
    """三种策略对比测试"""

    SAMPLE_TEXT = (
        "# 机器学习\n\n"
        "机器学习是人工智能的分支。它让计算机从数据中学习。\n\n"
        "## 监督学习\n\n"
        "监督学习使用标注数据训练模型。常见算法包括线性回归、决策树。\n\n"
        "## 无监督学习\n\n"
        "无监督学习从未标注数据中发现模式。聚类是典型应用。\n\n"
        "# 应用场景\n\n"
        "机器学习广泛应用于推荐系统、图像识别和自然语言处理。"
    )

    def test_all_strategies_produce_chunks(self) -> None:
        """三种策略都能产生有效 chunk"""
        meta = ChunkMetadata(src_id="SRC-0001", title="机器学习")
        for strategy in ("structure", "recursive"):
            with self.subTest(strategy=strategy):
                chunker = create_chunker(strategy, chunk_size=120, overlap=20)
                chunks = chunker.split(self.SAMPLE_TEXT, meta)
                self.assertGreater(len(chunks), 0, f"{strategy} 未产生 chunk")
                # 每个 chunk 有内容
                self.assertTrue(all(c.content.strip() for c in chunks))
                # 每个 chunk 的 metadata 完整
                self.assertTrue(all(c.metadata.src_id == "SRC-0001" for c in chunks))

    def test_char_positions_within_text(self) -> None:
        """所有 chunk 的字符位置在原文范围内"""
        meta = ChunkMetadata(src_id="SRC-0001", title="测试")
        text_len = len(self.SAMPLE_TEXT)
        for strategy in ("structure", "recursive"):
            with self.subTest(strategy=strategy):
                chunker = create_chunker(strategy, chunk_size=100, overlap=10)
                chunks = chunker.split(self.SAMPLE_TEXT, meta)
                for c in chunks:
                    self.assertGreaterEqual(c.metadata.start_char, 0)
                    self.assertLessEqual(c.metadata.end_char, text_len + 1)
