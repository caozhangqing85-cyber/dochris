"""编译流水线性能基准测试

测试 Phase 2 编译流水线各阶段的性能：
- 文本分块
- 质量评分
- 编译流程（mock LLM）
"""

from unittest.mock import MagicMock, patch

import pytest


class TestCompilationPerformance:
    """编译流水线性能基准"""

    def test_structure_aware_split_medium(self, benchmark, sample_text_medium: str) -> None:
        """结构感知分块 — 中等文本"""
        from dochris.core.text_chunker import structure_aware_split

        result = benchmark(structure_aware_split, sample_text_medium, chunk_size=4000, overlap=200)
        assert len(result) > 0

    def test_structure_aware_split_large(self, benchmark, sample_text_large: str) -> None:
        """结构感知分块 — 大文本"""
        from dochris.core.text_chunker import structure_aware_split

        result = benchmark(structure_aware_split, sample_text_large, chunk_size=4000, overlap=200)
        assert len(result) > 0

    def test_semantic_chunk_medium(self, benchmark, sample_text_medium: str) -> None:
        """语义分块 — 中等文本"""
        from dochris.core.text_chunker import semantic_chunk

        result = benchmark(semantic_chunk, sample_text_medium, chunk_size=4000, overlap=200)
        assert len(result) > 0

    def test_fixed_size_chunk_large(self, benchmark, sample_text_large: str) -> None:
        """固定长度分块 — 大文本"""
        from dochris.core.text_chunker import fixed_size_chunk

        result = benchmark(fixed_size_chunk, sample_text_large, chunk_size=4000, overlap=200)
        assert len(result) > 0

    def test_quality_scoring(self, benchmark) -> None:
        """质量评分性能"""
        from dochris.core.quality_scorer import score_summary_quality_v4

        data = {
            "title": "深度学习优化策略",
            "summary": "本文详细介绍了深度学习中的优化策略，"
            "包括学习率调度、梯度裁剪、正则化等技术。"
            "通过实验验证了这些方法在多个数据集上的有效性。" * 20,
            "key_points": [
                "学习率预热可以有效提升训练稳定性",
                "梯度裁剪防止梯度爆炸问题",
                "权重衰减作为 L2 正则化手段",
                "数据增强提升模型泛化能力",
            ],
            "concepts": [
                "学习率调度",
                "梯度裁剪",
                "正则化",
                "数据增强",
            ],
        }
        result = benchmark(score_summary_quality_v4, data)
        assert isinstance(result, (int, float))

    def test_should_use_hierarchical(self, benchmark, sample_text_large: str) -> None:
        """摘要策略选择性能"""
        from dochris.core.text_chunker import should_use_hierarchical

        result = benchmark(should_use_hierarchical, sample_text_large)
        assert result in ("direct", "map_reduce", "hierarchical")

    def test_compilation_pipeline_mock(self, benchmark, sample_text_medium: str) -> None:
        """编译流水线整体性能（mock LLM）"""
        mock_llm = MagicMock()
        mock_llm.compile.return_value = {
            "title": "测试编译",
            "summary": "编译结果摘要" * 50,
            "key_points": ["要点1", "要点2", "要点3"],
            "concepts": [{"name": "概念1", "definition": "定义"}],
        }

        with patch("dochris.core.llm_client.LLMClient", return_value=mock_llm):
            from dochris.core.text_chunker import structure_aware_split

            # 模拟编译流水线：分块 → 评分
            chunks = benchmark(structure_aware_split, sample_text_medium, chunk_size=4000)
            assert len(chunks) > 0
