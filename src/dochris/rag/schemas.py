"""RAG 统一数据模型

定义所有检索通道（关键词、向量、rerank）共享的候选与证据数据结构。
后续 Reranker、Eval、Observability、API 通过这些模型访问检索结果，
不再猜测分数语义。

归一化策略（逐项绝对归一化，跨查询可比较）：

- keyword score（整数累加）→ 1 - exp(-score/5)
  采用指数衰减而非 plan 中的 score/max 批次归一化，因为：
  1) 不依赖当前批次最大值，跨查询分数可比较
  2) 避免只有一个候选时 normalized_score 恒为 1.0 的边界问题
  score=5 → 0.63, score=10 → 0.86, score=15 → 0.95

- cosine distance（ChromaDB，[0, 2]）→ 1/(1+d)
  采用平滑衰减而非 plan 中的 1-min(d,1.0) 截断，因为：
  1) cosine distance 值域 [0, 2]，d>1 并非异常（向量方向相反）
  2) 截断到 0 会丢失远距离候选项之间的区分度
  d=0.1 → 0.91, d=0.5 → 0.67, d=1.0 → 0.50, d=2.0 → 0.33

- L2 distance（FAISS，[0, inf)）→ 1/(1+d)，与 plan 一致
  d=0.1 → 0.91, d=1.0 → 0.50, d=5.0 → 0.17

- rerank score → 直接裁剪到 [0, 1]
"""

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)


@dataclass
class RetrievalCandidate:
    """统一检索候选。

    所有后续方案（Reranker、Eval、Observability、API）通过此模型访问检索结果，
    不再猜测分数语义。normalized_score 是排序和比较的唯一依据。
    """

    id: str
    """候选唯一标识，如 'concept_SRC-0001_0' 或 'vec_SRC-0001_chunk_3'"""

    text: str
    """候选文本内容"""

    source: str
    """来源文件路径或标识"""

    channel: Literal["concept", "summary", "vector", "chunk"]
    """检索通道：concept/summary 为关键词，vector/chunk 为向量"""

    retriever: str
    """来源检索器标识，如 'keyword_concept'、'chromadb'、'faiss'"""

    raw_score: float
    """原始检索分数（未归一化）"""

    raw_distance: float | None = None
    """原始向量距离（仅向量通道有值）"""

    score_kind: Literal["keyword", "cosine_distance", "l2_distance", "rerank"] = "keyword"
    """分数语义，决定归一化策略"""

    normalized_score: float = 0.0
    """归一化到 [0, 1] 的分数，排序和比较的唯一依据"""

    rank: int | None = None
    """全局排名（跨通道归一化后排序），由 retrieve_candidates() 填充"""

    channel_rank: int | None = None
    """通道内排名（同一 retriever 中的原始排名），由 retrieve_candidates() 填充"""

    manifest_id: str | None = None
    """来源 manifest ID（如 SRC-0001）"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """额外元数据"""

    rerank_score: float | None = None
    """由 Reranker 填充的重排序分数"""

    def content_hash(self) -> str:
        """返回文本内容的短哈希，用于去重。"""
        return hashlib.md5(self.text.encode()).hexdigest()[:12]


@dataclass(frozen=True)
class SourceRef:
    """上下文中的来源引用信息，供 eval、citation、trace 使用。"""

    manifest_id: str | None
    """来源 manifest ID"""

    source: str
    """文件路径或标识"""

    channel: str
    """检索通道：concept / summary / vector / chunk"""

    text_hash: str
    """内容摘要哈希，用于去重和验证"""

    score: float
    """原始检索分数"""


# ============================================================
# 分数归一化工具
# ============================================================


def normalize_keyword_score(raw: float) -> float:
    """将关键词搜索的整数累加分归一化到 [0, 1]。

    关键词评分体系: 文件名精确 +10, 术语命中 +5, 文本命中 +1~3
    使用 1 - exp(-score/k) 映射，k=5 时:
      score=5 → 0.63, score=10 → 0.86, score=15 → 0.95
    """
    if raw <= 0:
        return 0.0
    return min(1.0, round(1.0 - math.exp(-raw / 5.0), 3))


def normalize_vector_score(raw_distance: float) -> float:
    """将向量距离转换为相似度 [0, 1]。

    支持 L2 (范围 [0, inf)) 和 cosine (范围 [0, 2]) 两种距离度量。
    使用 1/(1+d) 映射:
      d=0.1 → 0.91, d=0.5 → 0.67, d=1.0 → 0.50
    """
    if raw_distance < 0:
        logger.warning("向量距离为负数 (%.4f)，可能是上游数据错误", raw_distance)
        return 1.0
    return round(1.0 / (1.0 + raw_distance), 3)


def normalize_score(
    raw_score: float,
    score_kind: Literal["keyword", "cosine_distance", "l2_distance", "rerank"],
    raw_distance: float | None = None,
) -> float:
    """根据分数类型选择归一化策略。

    Args:
        raw_score: 原始分数
        score_kind: 分数语义
        raw_distance: 原始距离（仅向量通道需要）

    Returns:
        归一化到 [0, 1] 的分数
    """
    if score_kind == "keyword":
        return normalize_keyword_score(raw_score)
    elif score_kind in ("cosine_distance", "l2_distance"):
        return normalize_vector_score(raw_distance if raw_distance is not None else raw_score)
    elif score_kind == "rerank":
        return min(1.0, max(0.0, raw_score))
    return 0.0
