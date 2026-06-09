#!/usr/bin/env python3
"""测试 build_answer_context() 和 build_answer_prompt()

覆盖：
- 空输入、单一通道、混合通道的上下文构建
- 来源编号递增与 SourceRef 映射
- 字段缺失时的容错处理
- build_answer_prompt 的 system/user prompt 生成
"""

import hashlib
from unittest import TestCase

from dochris.rag.schemas import SourceRef
from dochris.phases.query_engine import build_answer_context, build_answer_prompt


class TestBuildAnswerContextEmpty(TestCase):
    """测试空输入"""

    def test_all_empty(self) -> None:
        """三个通道都为空时返回空字符串和空映射"""
        context, source_map = build_answer_context([], [], [])
        self.assertEqual(context, "")
        self.assertEqual(source_map, {})

    def test_concepts_only(self) -> None:
        """只有 concepts 时正常输出"""
        concepts = [
            {"name": "机器学习", "definition": "AI 子领域", "score": 10, "source": "wiki"}
        ]
        context, source_map = build_answer_context(concepts, [], [])
        self.assertIn("机器学习", context)
        self.assertIn("[S1]", context)
        self.assertIn("S1", source_map)
        self.assertEqual(source_map["S1"].channel, "concept")

    def test_summaries_only(self) -> None:
        """只有 summaries 时正常输出"""
        summaries = [
            {
                "title": "深度学习",
                "one_line": "使用多层神经网络",
                "key_points": ["反向传播", "梯度下降"],
                "score": 8,
                "source": "outputs",
            }
        ]
        context, source_map = build_answer_context([], summaries, [])
        self.assertIn("深度学习", context)
        self.assertIn("反向传播", context)
        self.assertEqual(source_map["S1"].channel, "summary")

    def test_vector_only(self) -> None:
        """只有 vector_results 时正常输出"""
        vectors = [
            {"text": "向量内容", "score": 0.3, "source": "test.md"}
        ]
        context, source_map = build_answer_context([], [], vectors)
        self.assertIn("向量内容", context)
        self.assertEqual(source_map["S1"].channel, "vector")


class TestBuildAnswerContextMixed(TestCase):
    """测试混合通道输入"""

    def _make_concept(self, idx: int, score: int = 10) -> dict:
        return {
            "name": f"概念{idx}",
            "definition": f"定义{idx}",
            "score": score,
            "source": "wiki",
            "manifest_id": f"SRC-{idx:04d}",
        }

    def _make_summary(self, idx: int, score: int = 8) -> dict:
        return {
            "title": f"摘要{idx}",
            "one_line": f"一句话{idx}",
            "key_points": [f"要点{idx}"],
            "score": score,
            "source": "outputs",
            "manifest_id": f"SRC-{idx:04d}",
        }

    def _make_vector(self, idx: int, score: float = 0.5) -> dict:
        return {
            "text": f"向量内容{idx}",
            "score": score,
            "source": f"file{idx}.md",
        }

    def test_source_numbering_across_channels(self) -> None:
        """来源编号跨通道连续递增"""
        concepts = [self._make_concept(1), self._make_concept(2)]
        summaries = [self._make_summary(3)]
        vectors = [self._make_vector(4)]

        context, source_map = build_answer_context(concepts, summaries, vectors)

        # 应该有 4 个来源：S1, S2, S3, S4
        self.assertEqual(len(source_map), 4)
        self.assertIn("S1", source_map)
        self.assertIn("S4", source_map)

        # 通道顺序正确
        self.assertEqual(source_map["S1"].channel, "concept")
        self.assertEqual(source_map["S2"].channel, "concept")
        self.assertEqual(source_map["S3"].channel, "summary")
        self.assertEqual(source_map["S4"].channel, "vector")

    def test_source_ref_fields(self) -> None:
        """SourceRef 字段正确填充"""
        concepts = [
            {
                "name": "测试",
                "definition": "定义文本",
                "score": 15,
                "source": "wiki",
                "manifest_id": "SRC-0001",
            }
        ]
        _, source_map = build_answer_context(concepts, [], [])

        ref = source_map["S1"]
        self.assertIsInstance(ref, SourceRef)
        self.assertEqual(ref.manifest_id, "SRC-0001")
        self.assertEqual(ref.source, "wiki")
        self.assertEqual(ref.channel, "concept")
        self.assertEqual(ref.score, 15.0)
        expected_hash = hashlib.md5("定义文本".encode()).hexdigest()[:12]
        self.assertEqual(ref.text_hash, expected_hash)

    def test_context_sections_separated(self) -> None:
        """各通道有独立的章节标题"""
        context, _ = build_answer_context(
            [self._make_concept(1)],
            [self._make_summary(2)],
            [self._make_vector(3)],
        )
        self.assertIn("### 相关概念", context)
        self.assertIn("### 相关资料", context)
        self.assertIn("### 向量检索结果", context)

    def test_vector_text_truncated(self) -> None:
        """向量内容超过 300 字符时截断"""
        long_text = "A" * 500
        vectors = [{"text": long_text, "score": 0.3, "source": "test.md"}]
        context, source_map = build_answer_context([], [], vectors)

        # SourceRef 的 text_hash 应基于截断后的文本
        expected_hash = hashlib.md5(long_text[:300].encode()).hexdigest()[:12]
        self.assertEqual(source_map["S1"].text_hash, expected_hash)


class TestBuildAnswerContextEdgeCases(TestCase):
    """测试边界和容错"""

    def test_missing_fields_graceful(self) -> None:
        """字段缺失时优雅降级"""
        concepts = [{}]
        context, source_map = build_answer_context(concepts, [], [])
        # 不应崩溃
        self.assertIn("S1", source_map)
        self.assertEqual(source_map["S1"].score, 0.0)
        self.assertEqual(source_map["S1"].source, "")

    def test_definition_fallback_to_explanation(self) -> None:
        """concept 的 definition 字段缺失时回退到 explanation"""
        concepts = [
            {"name": "测试", "explanation": "解释文本", "score": 5, "source": "wiki"}
        ]
        context, _ = build_answer_context(concepts, [], [])
        self.assertIn("解释文本", context)

    def test_vector_text_fallback_chain(self) -> None:
        """vector 的 text 字段缺失时依次回退到 definition → content"""
        vectors = [{"definition": "定义内容", "score": 0.3, "source": "test.md"}]
        context, _ = build_answer_context([], [], vectors)
        self.assertIn("定义内容", context)

        vectors2 = [{"content": "内容文本", "score": 0.3, "source": "test.md"}]
        context2, _ = build_answer_context([], [], vectors2)
        self.assertIn("内容文本", context2)

    def test_summary_key_points_included(self) -> None:
        """摘要的 key_points 以列表形式包含在上下文中"""
        summaries = [
            {
                "title": "测试",
                "one_line": "一句话",
                "key_points": ["要点A", "要点B"],
                "score": 5,
                "source": "wiki",
            }
        ]
        context, _ = build_answer_context([], summaries, [])
        self.assertIn("要点A", context)
        self.assertIn("要点B", context)

    def test_summary_key_points_missing(self) -> None:
        """摘要无 key_points 时不崩溃"""
        summaries = [
            {"title": "测试", "one_line": "一句话", "score": 5, "source": "wiki"}
        ]
        context, _ = build_answer_context([], summaries, [])
        self.assertIn("测试", context)


class TestBuildAnswerPrompt(TestCase):
    """测试 build_answer_prompt() 函数"""

    def test_empty_context(self) -> None:
        """空上下文时返回合理的 prompt"""
        system_prompt, user_prompt, concepts_set = build_answer_prompt(
            "", "测试问题", []
        )
        self.assertIsInstance(system_prompt, str)
        self.assertIsInstance(user_prompt, str)
        self.assertIn("测试问题", user_prompt)

    def test_with_context(self) -> None:
        """有上下文时 prompt 包含查询"""
        context = "[S1] **测试**: 内容"
        system_prompt, user_prompt, _ = build_answer_prompt(
            context, "查询内容", []
        )
        self.assertIn("查询内容", user_prompt)

    def test_concepts_set_populated(self) -> None:
        """concepts 集合正确填充"""
        concepts = [
            {"name": "机器学习"},
            {"name": "深度学习"},
        ]
        _, _, concepts_set = build_answer_prompt("context", "query", concepts)
        self.assertIn("机器学习", concepts_set)
        self.assertIn("深度学习", concepts_set)
