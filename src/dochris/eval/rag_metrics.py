"""RAG 评估指标计算

检索指标（不需要 LLM）：
- recall@k：期望来源中出现在 top-k 的比例
- precision@k：top-k 结果中命中期望来源的比例
- mrr：第一个正确结果的倒数排名（Mean Reciprocal Rank）
- ndcg@k：归一化折损累积增益（Normalized Discounted Cumulative Gain）

所有指标值域 [0, 1]，越高越好。

用法：
    metrics = compute_retrieval_metrics(
        retrieved_ids=["SRC-0001", "SRC-0002", "SRC-0003"],
        expected_ids=["SRC-0001", "SRC-0004"],
        k=5,
    )
    # metrics = {"recall@5": 0.5, "precision@5": 0.333, "mrr": 1.0, "ndcg@5": 0.5}
"""

from __future__ import annotations

import math

from dochris.eval.schemas import QueryEvidence, RAGEvalResult, RAGEvalSample


def compute_retrieval_metrics(
    retrieved_ids: list[str],
    expected_ids: list[str],
    k: int = 5,
) -> dict[str, float]:
    """计算单条样本的检索指标。

    Args:
        retrieved_ids: 检索结果的 manifest_id 列表（按排名排序）
        expected_ids: 期望命中的 manifest_id 列表
        k: 截断位置

    Returns:
        指标字典 {"recall@k", "precision@k", "mrr", "ndcg@k"}
    """
    if not expected_ids:
        # 无期望来源时跳过检索指标
        return {}

    top_k = retrieved_ids[:k]
    expected_set = set(expected_ids)

    # 命中集合（去重：同一文档出现多次只算一次）
    hits_set = expected_set & set(top_k)

    recall = len(hits_set) / len(expected_set) if expected_set else 0.0
    precision = len(hits_set) / k if k > 0 else 0.0
    mrr = _compute_mrr(top_k, expected_set)
    ndcg = _compute_ndcg(top_k, expected_set, k)

    return {
        f"recall@{k}": round(recall, 4),
        f"precision@{k}": round(precision, 4),
        "mrr": round(mrr, 4),
        f"ndcg@{k}": round(ndcg, 4),
    }


def _compute_mrr(top_k: list[str], expected_set: set[str]) -> float:
    """计算 MRR（Mean Reciprocal Rank）。

    第一个正确结果的倒数排名。
    MRR = 1/rank_of_first_correct

    Args:
        top_k: 前 k 个检索结果的 ID
        expected_set: 期望 ID 集合

    Returns:
        MRR 值 [0, 1]
    """
    for i, mid in enumerate(top_k, 1):
        if mid in expected_set:
            return 1.0 / i
    return 0.0


def _compute_ndcg(top_k: list[str], expected_set: set[str], k: int = 5) -> float:
    """计算 NDCG（Normalized Discounted Cumulative Gain）。

    DCG = Σ (relevance / log2(rank + 1))  每个期望 ID 最多贡献一次
    IDCG = Σ (1 / log2(rank + 1))  for min(|expected|, k) items
    NDCG = DCG / IDCG

    简化：相关性为二元（命中=1，未命中=0）。

    Args:
        top_k: 前 k 个检索结果的 ID
        expected_set: 期望 ID 集合
        k: 截断位置（用于 IDCG 计算）

    Returns:
        NDCG 值 [0, 1]
    """
    if not expected_set:
        return 0.0

    # DCG：实际排序下的增益（去重：每个期望 ID 最多贡献一次）
    dcg = 0.0
    seen: set[str] = set()
    for i, mid in enumerate(top_k, 1):
        if mid in expected_set and mid not in seen:
            dcg += 1.0 / math.log2(i + 1)
            seen.add(mid)

    # IDCG：最优排序下的增益（min(|expected|, k) 个期望文档排最前）
    idcg = 0.0
    for i in range(1, min(len(expected_set), k) + 1):
        idcg += 1.0 / math.log2(i + 1)

    return dcg / idcg if idcg > 0 else 0.0


def evaluate_sample(
    sample: RAGEvalSample,
    evidence: list[QueryEvidence],
    k: int = 5,
) -> RAGEvalResult:
    """评估单个样本，计算检索指标并归因失败。

    Args:
        sample: 评估样本（含期望来源）
        evidence: 实际检索到的证据列表
        k: 截断位置

    Returns:
        RAGEvalResult 含指标和失败归因
    """
    # 提取检索到的 manifest_id 列表
    retrieved_ids = [
        e.manifest_id for e in evidence if e.manifest_id is not None
    ]

    # 计算检索指标
    metrics = compute_retrieval_metrics(
        retrieved_ids=retrieved_ids,
        expected_ids=sample.expected_source_ids,
        k=k,
    )

    # 失败归因
    failures: list[str] = []
    if sample.expected_source_ids:
        retrieved_set = set(retrieved_ids)
        expected_set = set(sample.expected_source_ids)
        missed = expected_set - retrieved_set
        for mid in sorted(missed):
            failures.append(f"retrieval_miss: {mid} 未命中")

    return RAGEvalResult(
        sample_id=sample.id,
        question=sample.question,
        answer="",  # generation 指标后续迭代
        evidence=evidence,
        metrics=metrics,
        failures=failures,
    )


def aggregate_metrics(results: list[RAGEvalResult]) -> dict[str, float]:
    """聚合多条评估结果的指标均值。

    Args:
        results: 评估结果列表

    Returns:
        均值指标字典
    """
    if not results:
        return {}

    all_metrics: dict[str, list[float]] = {}
    for r in results:
        for key, value in r.metrics.items():
            all_metrics.setdefault(key, []).append(value)

    summary: dict[str, float] = {}
    for key, values in all_metrics.items():
        summary[f"avg_{key}"] = round(sum(values) / len(values), 4)

    return summary
