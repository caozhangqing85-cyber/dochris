"""RAG 评估数据模型

定义评估样本、查询证据、评估结果和汇总报告的数据结构。

指标体系（第一版实现 retrieval 指标，generation 指标后续迭代）：
- recall@k：期望来源中出现在 top-k 的比例
- precision@k：top-k 结果中命中期望来源的比例
- MRR：第一个正确结果的倒数排名
- NDCG@k：考虑排序位置的归一化折损累积增益
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class RAGEvalSample:
    """RAG 评估样本。

    从 golden JSONL 文件加载，每条样本包含一个问题、期望来源和可选的标准答案。
    """

    id: str
    """样本唯一标识"""

    question: str
    """评估用查询问题"""

    expected_source_ids: list[str] = field(default_factory=list)
    """期望命中的 manifest ID 列表（如 ['SRC-0001', 'SRC-0003']）"""

    ground_truth: str | None = None
    """可选的标准答案文本，用于 generation 指标"""

    tags: list[str] = field(default_factory=list)
    """分类标签（如 ['技术', '数学']）"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """额外元数据"""


@dataclass(frozen=True)
class QueryEvidence:
    """一次查询实际使用的证据。

    记录检索结果中的每条证据及其来源、分数、排名，
    供评估指标计算和失败归因使用。
    """

    text: str
    """证据文本"""

    source: str
    """来源文件路径或标识"""

    manifest_id: str | None
    """来源 manifest ID（如 SRC-0001）"""

    score: float
    """检索分数（归一化后）"""

    rank: int
    """在检索结果中的排名（1-based）"""

    channel: Literal["keyword", "vector", "rerank"]
    """检索通道"""

    original_query: str | None = None
    """记录 pre_query hook 改写前的原始 query（如有）"""


@dataclass
class RAGEvalResult:
    """单条样本评估结果。"""

    sample_id: str
    """样本 ID"""

    question: str
    """查询问题"""

    answer: str
    """LLM 生成的回答"""

    evidence: list[QueryEvidence] = field(default_factory=list)
    """实际使用的证据列表"""

    metrics: dict[str, float] = field(default_factory=dict)
    """评估指标（recall@k, precision@k, mrr, ndcg 等）"""

    failures: list[str] = field(default_factory=list)
    """失败归因（如 'retrieval_miss: SRC-0003 未命中'）"""


@dataclass
class RAGEvalReport:
    """评估汇总报告。"""

    dataset: str
    """数据集名称或路径"""

    timestamp: str
    """评估时间戳（ISO 8601）"""

    sample_count: int
    """样本总数"""

    results: list[RAGEvalResult] = field(default_factory=list)
    """逐条评估结果"""

    summary: dict[str, float] = field(default_factory=dict)
    """汇总指标均值（avg_recall@k, avg_precision@k, avg_mrr, avg_ndcg）"""

    config: dict[str, Any] = field(default_factory=dict)
    """评估配置快照（reranker_enabled, candidate_k 等）"""

    def compute_summary(self) -> None:
        """从 results 计算 summary 均值。"""
        if not self.results:
            return

        # 收集所有指标
        all_metrics: dict[str, list[float]] = {}
        for r in self.results:
            for key, value in r.metrics.items():
                all_metrics.setdefault(key, []).append(value)

        # 计算均值
        for key, values in all_metrics.items():
            self.summary[f"avg_{key}"] = round(sum(values) / len(values), 4)
