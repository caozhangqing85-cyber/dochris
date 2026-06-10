"""RAG 评估执行器

批量执行查询、收集上下文、计算指标、生成报告。

用法：
    from dochris.eval.runner import RAGEvaluator
    from dochris.eval.datasets import load_dataset

    samples = load_dataset("eval/rag_golden.jsonl")
    evaluator = RAGEvaluator()
    report = await evaluator.evaluate_dataset(samples)
    evaluator.save_report(report, "reports/rag-eval-20260610.json")
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dochris.eval.rag_metrics import aggregate_metrics, evaluate_sample
from dochris.eval.schemas import QueryEvidence, RAGEvalReport, RAGEvalResult, RAGEvalSample

logger = logging.getLogger(__name__)


class RAGEvaluator:
    """RAG 评估执行器。

    批量执行查询、收集证据、计算检索指标、生成汇总报告。

    Args:
        k: 检索指标截断位置（默认 5）
        rerank: 是否启用 Reranker
        mode: 查询模式
    """

    def __init__(
        self,
        k: int = 5,
        rerank: bool = False,
        mode: str = "combined",
    ) -> None:
        self.k = k
        self.rerank = rerank
        self.mode = mode

    async def evaluate_sample(
        self,
        sample: RAGEvalSample,
    ) -> RAGEvalResult:
        """执行一次查询并评估检索指标。

        Args:
            sample: 评估样本

        Returns:
            RAGEvalResult 含指标和失败归因
        """
        from dochris.phases.phase3_query import query_async

        try:
            result = await query_async(
                sample.question,
                mode=self.mode,
                top_k=self.k,
                rerank=self.rerank,
            )
        except Exception as e:
            logger.warning("样本 %s 查询失败: %s", sample.id, e)
            return RAGEvalResult(
                sample_id=sample.id,
                question=sample.question,
                answer="",
                evidence=[],
                metrics={},
                failures=[f"query_error: {e}"],
            )

        # 将检索结果转为 QueryEvidence
        evidence = self._extract_evidence(result)

        # 计算检索指标
        eval_result = evaluate_sample(sample, evidence, k=self.k)
        # 直接复用本次查询的 answer，避免二次查询
        eval_result.answer = result.get("answer", "")
        return eval_result

    async def evaluate_dataset(
        self,
        samples: list[RAGEvalSample],
    ) -> RAGEvalReport:
        """批量评估并输出汇总报告。

        Args:
            samples: 评估样本列表

        Returns:
            RAGEvalReport 含逐条结果和汇总指标
        """
        results: list[RAGEvalResult] = []

        for i, sample in enumerate(samples, 1):
            logger.info("评估样本 %d/%d: %s", i, len(samples), sample.id)
            eval_result = await self.evaluate_sample(sample)
            results.append(eval_result)

        # 汇总
        summary = aggregate_metrics(results)
        config = {
            "k": self.k,
            "rerank": self.rerank,
            "mode": self.mode,
            "sample_count": len(samples),
        }

        report = RAGEvalReport(
            dataset=f"eval_{len(samples)}_samples",
            timestamp=datetime.now(tz=UTC).isoformat(),
            sample_count=len(samples),
            results=results,
            summary=summary,
            config=config,
        )

        logger.info("评估完成: %d 样本, 指标: %s", len(samples), summary)
        return report

    def _extract_evidence(self, query_result: dict[str, Any]) -> list[QueryEvidence]:
        """从查询结果中提取证据列表。

        将 concepts、summaries、vector_results 转为统一的 QueryEvidence 列表。
        """
        evidence: list[QueryEvidence] = []
        rank = 0

        # Concepts
        for item in query_result.get("concepts", []):
            rank += 1
            evidence.append(
                QueryEvidence(
                    text=item.get("definition", item.get("content", "")),
                    source=item.get("source", ""),
                    manifest_id=item.get("manifest_id"),
                    score=item.get("score", 0.0),
                    rank=rank,
                    channel="keyword",
                )
            )

        # Summaries
        for item in query_result.get("summaries", []):
            rank += 1
            evidence.append(
                QueryEvidence(
                    text=item.get("content", item.get("text", "")),
                    source=item.get("source", ""),
                    manifest_id=item.get("manifest_id"),
                    score=item.get("score", 0.0),
                    rank=rank,
                    channel="keyword",
                )
            )

        # Vector results
        for item in query_result.get("vector_results", []):
            rank += 1
            evidence.append(
                QueryEvidence(
                    text=item.get("text", ""),
                    source=item.get("source", ""),
                    manifest_id=item.get("manifest_id"),
                    score=item.get("score", 0.0),
                    rank=rank,
                    channel="vector",
                )
            )

        return evidence

    @staticmethod
    def save_report(report: RAGEvalReport, path: str | Path) -> None:
        """将评估报告保存为 JSON 文件。

        Args:
            report: 评估报告
            path: 输出路径
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "dataset": report.dataset,
            "timestamp": report.timestamp,
            "sample_count": report.sample_count,
            "summary": report.summary,
            "config": report.config,
            "results": [
                {
                    "sample_id": r.sample_id,
                    "question": r.question,
                    "answer": r.answer[:200] if r.answer else "",
                    "metrics": r.metrics,
                    "failures": r.failures,
                    "evidence_count": len(r.evidence),
                }
                for r in report.results
            ],
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info("评估报告已保存: %s", path)

    @staticmethod
    def save_report_markdown(report: RAGEvalReport, path: str | Path) -> None:
        """将评估报告保存为 Markdown 文件。

        Args:
            report: 评估报告
            path: 输出路径
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "# RAG 评估报告",
            "",
            f"- **数据集**: {report.dataset}",
            f"- **时间**: {report.timestamp}",
            f"- **样本数**: {report.sample_count}",
            "",
            "## 配置",
            "",
        ]
        for key, value in report.config.items():
            lines.append(f"- {key}: {value}")

        lines.extend([
            "",
            "## 汇总指标",
            "",
            "| 指标 | 值 |",
            "|------|-----|",
        ])
        for key, value in report.summary.items():
            lines.append(f"| {key} | {value:.4f} |")

        # 失败样本
        failed = [r for r in report.results if r.failures]
        if failed:
            lines.extend([
                "",
                f"## 失败样本 ({len(failed)})",
                "",
            ])
            for r in failed[:10]:
                lines.append(f"### {r.sample_id}: {r.question}")
                lines.append(f"- 指标: {r.metrics}")
                lines.append(f"- 失败: {', '.join(r.failures)}")
                lines.append("")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info("Markdown 报告已保存: %s", path)
