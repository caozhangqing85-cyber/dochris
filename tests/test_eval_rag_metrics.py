#!/usr/bin/env python3
"""RAG 评估指标测试

覆盖：
- recall@k, precision@k, MRR, NDCG 固定输入输出
- 无期望来源时跳过指标
- evaluate_sample() 端到端测试
- aggregate_metrics() 均值计算
- datasets JSONL 加载/保存
"""

import tempfile
from pathlib import Path
from unittest import TestCase

from dochris.eval.rag_metrics import (
    aggregate_metrics,
    compute_retrieval_metrics,
    evaluate_sample,
)
from dochris.eval.schemas import (
    QueryEvidence,
    RAGEvalReport,
    RAGEvalResult,
    RAGEvalSample,
)

# ============================================================
# 检索指标测试
# ============================================================


class TestRecallAtK(TestCase):
    """recall@k 测试"""

    def test_perfect_recall(self) -> None:
        """所有期望来源都命中"""
        metrics = compute_retrieval_metrics(
            retrieved_ids=["A", "B", "C"],
            expected_ids=["A", "B"],
            k=5,
        )
        self.assertEqual(metrics["recall@5"], 1.0)

    def test_partial_recall(self) -> None:
        """部分命中"""
        metrics = compute_retrieval_metrics(
            retrieved_ids=["A", "C"],
            expected_ids=["A", "B"],
            k=5,
        )
        self.assertEqual(metrics["recall@5"], 0.5)

    def test_zero_recall(self) -> None:
        """全部未命中"""
        metrics = compute_retrieval_metrics(
            retrieved_ids=["C", "D"],
            expected_ids=["A", "B"],
            k=5,
        )
        self.assertEqual(metrics["recall@5"], 0.0)

    def test_k_truncation(self) -> None:
        """k 截断影响 recall"""
        metrics = compute_retrieval_metrics(
            retrieved_ids=["C", "D", "A", "B"],
            expected_ids=["A", "B"],
            k=2,
        )
        # top-2 中没有 A/B
        self.assertEqual(metrics["recall@2"], 0.0)


class TestPrecisionAtK(TestCase):
    """precision@k 测试"""

    def test_perfect_precision(self) -> None:
        """全部命中"""
        metrics = compute_retrieval_metrics(
            retrieved_ids=["A", "B"],
            expected_ids=["A", "B"],
            k=5,
        )
        self.assertEqual(metrics["precision@5"], 1.0)

    def test_partial_precision(self) -> None:
        """部分命中"""
        metrics = compute_retrieval_metrics(
            retrieved_ids=["A", "C", "D"],
            expected_ids=["A", "B"],
            k=3,
        )
        # 3 个结果中 1 个命中 → 0.333
        self.assertAlmostEqual(metrics["precision@3"], 1 / 3, places=3)

    def test_zero_precision(self) -> None:
        """全部未命中"""
        metrics = compute_retrieval_metrics(
            retrieved_ids=["C", "D"],
            expected_ids=["A", "B"],
            k=5,
        )
        self.assertEqual(metrics["precision@5"], 0.0)


class TestMRR(TestCase):
    """MRR（Mean Reciprocal Rank）测试"""

    def test_first_position_hit(self) -> None:
        """第一个就命中 → MRR = 1.0"""
        metrics = compute_retrieval_metrics(
            retrieved_ids=["A", "B", "C"],
            expected_ids=["A"],
            k=5,
        )
        self.assertEqual(metrics["mrr"], 1.0)

    def test_second_position_hit(self) -> None:
        """第二个命中 → MRR = 0.5"""
        metrics = compute_retrieval_metrics(
            retrieved_ids=["C", "A", "B"],
            expected_ids=["A"],
            k=5,
        )
        self.assertEqual(metrics["mrr"], 0.5)

    def test_no_hit(self) -> None:
        """未命中 → MRR = 0.0"""
        metrics = compute_retrieval_metrics(
            retrieved_ids=["C", "D"],
            expected_ids=["A"],
            k=5,
        )
        self.assertEqual(metrics["mrr"], 0.0)


class TestNDCG(TestCase):
    """NDCG（Normalized Discounted Cumulative Gain）测试"""

    def test_perfect_ndcg(self) -> None:
        """完美排序 → NDCG = 1.0"""
        metrics = compute_retrieval_metrics(
            retrieved_ids=["A", "B"],
            expected_ids=["A", "B"],
            k=5,
        )
        self.assertEqual(metrics["ndcg@5"], 1.0)

    def test_partial_hit_ndcg(self) -> None:
        """部分命中 → 0 < NDCG < 1.0"""
        metrics = compute_retrieval_metrics(
            retrieved_ids=["C", "D", "A"],
            expected_ids=["A", "B"],
            k=3,
        )
        # 3 个结果中只有 A 命中，B 缺失
        self.assertGreater(metrics["ndcg@3"], 0.0)
        self.assertLess(metrics["ndcg@3"], 1.0)

    def test_no_hit(self) -> None:
        """未命中 → NDCG = 0.0"""
        metrics = compute_retrieval_metrics(
            retrieved_ids=["C", "D"],
            expected_ids=["A"],
            k=5,
        )
        self.assertEqual(metrics["ndcg@5"], 0.0)


class TestEmptyExpected(TestCase):
    """无期望来源时跳过指标"""

    def test_empty_expected_returns_empty(self) -> None:
        """expected_ids 为空时返回空指标"""
        metrics = compute_retrieval_metrics(
            retrieved_ids=["A", "B"],
            expected_ids=[],
            k=5,
        )
        self.assertEqual(metrics, {})


# ============================================================
# evaluate_sample 端到端测试
# ============================================================


class TestEvaluateSample(TestCase):
    """evaluate_sample() 端到端测试"""

    def test_perfect_retrieval(self) -> None:
        """完美检索：全部命中"""
        sample = RAGEvalSample(
            id="q1",
            question="什么是机器学习？",
            expected_source_ids=["SRC-0001"],
        )
        evidence = [
            QueryEvidence(
                text="机器学习是人工智能的子领域...",
                source="ml_intro.pdf",
                manifest_id="SRC-0001",
                score=0.9,
                rank=1,
                channel="keyword",
            )
        ]

        result = evaluate_sample(sample, evidence, k=5)

        self.assertEqual(result.sample_id, "q1")
        self.assertEqual(result.metrics["recall@5"], 1.0)
        self.assertEqual(result.metrics["precision@5"], 1.0)
        self.assertEqual(len(result.failures), 0)

    def test_missed_retrieval(self) -> None:
        """检索缺失：期望来源未命中"""
        sample = RAGEvalSample(
            id="q2",
            question="深度学习原理",
            expected_source_ids=["SRC-0001", "SRC-0002"],
        )
        evidence = [
            QueryEvidence(
                text="不相关内容",
                source="other.pdf",
                manifest_id="SRC-0003",
                score=0.5,
                rank=1,
                channel="vector",
            )
        ]

        result = evaluate_sample(sample, evidence, k=5)

        self.assertEqual(result.metrics["recall@5"], 0.0)
        # 应该有 2 个失败归因
        self.assertEqual(len(result.failures), 2)
        self.assertTrue(any("SRC-0001" in f for f in result.failures))
        self.assertTrue(any("SRC-0002" in f for f in result.failures))

    def test_no_expected_sources(self) -> None:
        """无期望来源时不计算检索指标"""
        sample = RAGEvalSample(
            id="q3",
            question="自由问题",
            expected_source_ids=[],
        )
        evidence = [
            QueryEvidence(
                text="一些内容",
                source="doc.pdf",
                manifest_id="SRC-0001",
                score=0.8,
                rank=1,
                channel="keyword",
            )
        ]

        result = evaluate_sample(sample, evidence, k=5)
        self.assertEqual(result.metrics, {})
        self.assertEqual(len(result.failures), 0)


# ============================================================
# aggregate_metrics 测试
# ============================================================


class TestAggregateMetrics(TestCase):
    """aggregate_metrics() 均值计算"""

    def test_averages(self) -> None:
        """多结果均值计算"""
        results = [
            RAGEvalResult(
                sample_id="q1",
                question="test",
                answer="",
                metrics={"recall@5": 1.0, "mrr": 1.0},
            ),
            RAGEvalResult(
                sample_id="q2",
                question="test",
                answer="",
                metrics={"recall@5": 0.5, "mrr": 0.5},
            ),
        ]

        summary = aggregate_metrics(results)

        self.assertAlmostEqual(summary["avg_recall@5"], 0.75, places=3)
        self.assertAlmostEqual(summary["avg_mrr"], 0.75, places=3)

    def test_empty_results(self) -> None:
        """空结果返回空"""
        summary = aggregate_metrics([])
        self.assertEqual(summary, {})


# ============================================================
# datasets 测试
# ============================================================


class TestDatasetIO(TestCase):
    """JSONL 数据集加载/保存"""

    def test_load_dataset(self) -> None:
        """加载 JSONL 数据集"""
        from dochris.eval.datasets import load_dataset

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write('{"id": "q1", "question": "什么是AI？", "expected_source_ids": ["SRC-0001"]}\n')
            f.write('{"id": "q2", "question": "深度学习原理", "expected_source_ids": ["SRC-0002"], "ground_truth": "DL是..."}\n')
            f.write("# 注释行\n")
            f.write("\n")
            f.flush()

            samples = load_dataset(f.name)

        self.assertEqual(len(samples), 2)
        self.assertEqual(samples[0].id, "q1")
        self.assertEqual(samples[0].question, "什么是AI？")
        self.assertEqual(samples[1].ground_truth, "DL是...")

        # 清理
        Path(f.name).unlink()

    def test_save_and_reload(self) -> None:
        """保存后重新加载，验证往返"""
        from dochris.eval.datasets import load_dataset, save_dataset

        samples = [
            RAGEvalSample(id="q1", question="测试问题", expected_source_ids=["SRC-0001"]),
            RAGEvalSample(
                id="q2",
                question="带答案的问题",
                expected_source_ids=["SRC-0002"],
                ground_truth="标准答案",
                tags=["技术"],
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.jsonl"
            save_dataset(samples, path)

            # 验证文件存在
            self.assertTrue(path.exists())

            # 重新加载
            loaded = load_dataset(path)
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[0].id, "q1")
            self.assertEqual(loaded[1].ground_truth, "标准答案")
            self.assertEqual(loaded[1].tags, ["技术"])

    def test_load_nonexistent_file_raises(self) -> None:
        """加载不存在的文件抛出 FileNotFoundError"""
        from dochris.eval.datasets import load_dataset

        with self.assertRaises(FileNotFoundError):
            load_dataset("/nonexistent/path.jsonl")

    def test_generate_sample_questions(self) -> None:
        """自动生成基础评估样本"""
        from dochris.eval.datasets import generate_sample_questions

        samples = generate_sample_questions(
            manifest_ids=["SRC-0001", "SRC-0002", "SRC-0003"],
            titles={"SRC-0001": "机器学习", "SRC-0002": "深度学习", "SRC-0003": "NLP"},
            count=2,
        )

        self.assertEqual(len(samples), 2)
        self.assertIn("机器学习", samples[0].question)
        self.assertEqual(samples[0].expected_source_ids, ["SRC-0001"])


class TestRAGEvalReportSchema(TestCase):
    """RAGEvalReport 数据结构测试"""

    def test_compute_summary(self) -> None:
        """compute_summary 从 results 计算均值"""
        report = RAGEvalReport(
            dataset="test",
            timestamp="2026-06-10T00:00:00Z",
            sample_count=2,
            results=[
                RAGEvalResult(
                    sample_id="q1",
                    question="test",
                    answer="",
                    metrics={"recall@5": 1.0, "mrr": 1.0},
                ),
                RAGEvalResult(
                    sample_id="q2",
                    question="test",
                    answer="",
                    metrics={"recall@5": 0.5, "mrr": 0.0},
                ),
            ],
        )

        report.compute_summary()

        self.assertAlmostEqual(report.summary["avg_recall@5"], 0.75, places=3)
        self.assertAlmostEqual(report.summary["avg_mrr"], 0.5, places=3)

    def test_empty_report_summary(self) -> None:
        """空报告 compute_summary 不报错"""
        report = RAGEvalReport(
            dataset="empty",
            timestamp="2026-06-10T00:00:00Z",
            sample_count=0,
        )
        report.compute_summary()
        self.assertEqual(report.summary, {})
