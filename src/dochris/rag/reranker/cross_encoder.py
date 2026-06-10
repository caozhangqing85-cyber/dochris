"""CrossEncoder Reranker — 基于 sentence_transformers.CrossEncoder

默认轻量实现，使用 cross-encoder 对 query-document pair 打分。
支持所有兼容 CrossEncoder 的模型（BGE reranker、MS MARCO 等）。

模型加载策略：
- 首次调用 rerank() 时延迟加载模型（lazy init），避免 import 时阻塞
- model_name 从 Settings.reranker_model 读取，默认 BAAI/bge-reranker-base
- 小模型（如 cross-encoder/ms-marco-MiniLM-L-6-v2）可在 CPU 上运行
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from dochris.rag.reranker.base import BaseReranker

if TYPE_CHECKING:
    from dochris.rag.schemas import RetrievalCandidate

logger = logging.getLogger(__name__)


class CrossEncoderReranker(BaseReranker):
    """基于 sentence_transformers.CrossEncoder 的 Reranker。

    Args:
        model_name: CrossEncoder 模型名称或路径
        max_length: 输入最大 token 长度（默认 512）
        device: 推理设备（auto/cpu/cuda/mps），默认 auto
    """

    name = "cross_encoder"

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-base",
        max_length: int = 512,
        device: str = "auto",
    ) -> None:
        self._model_name = model_name
        self._max_length = max_length
        self._device = device
        self._model = None

    def _ensure_model(self) -> None:
        """延迟加载模型，首次调用时初始化。"""
        if self._model is not None:
            return
        try:
            from sentence_transformers import CrossEncoder
        except ImportError:
            raise ImportError(
                "sentence-transformers 未安装，无法使用 CrossEncoder Reranker。\n"
                "安装命令: pip install sentence-transformers"
            ) from None

        logger.info("加载 CrossEncoder 模型: %s (device=%s)", self._model_name, self._device)
        self._model = CrossEncoder(
            self._model_name,
            max_length=self._max_length,
            device=self._device if self._device != "auto" else None,
        )
        logger.info("CrossEncoder 模型加载完成")

    def rerank(
        self,
        query: str,
        candidates: list[RetrievalCandidate],
        top_k: int = 5,
    ) -> list[RetrievalCandidate]:
        """使用 CrossEncoder 对候选重排序。

        流程：
        1. 构建 (query, candidate_text) pair 列表
        2. CrossEncoder 批量推理得到相关性分数
        3. 按分数降序排序，取 top_k
        4. 将分数归一化到 [0, 1] 写入 rerank_score

        Args:
            query: 用户查询文本
            candidates: 已归一化的检索候选列表
            top_k: 最终返回的候选数量

        Returns:
            重排序后的候选列表
        """
        if not candidates:
            return []

        self._ensure_model()

        # 构建 query-document pairs
        pairs = [(query, c.text) for c in candidates]

        # 批量推理
        scores = self._model.predict(pairs, batch_size=32, show_progress_bar=False)

        # 按分数降序排序
        scored_candidates = list(zip(candidates, scores, strict=True))
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        # 归一化 rerank score 到 [0, 1]
        max_score = scored_candidates[0][1] if scored_candidates else 1.0
        min_score = scored_candidates[-1][1] if scored_candidates else 0.0
        score_range = max_score - min_score if max_score != min_score else 1.0

        results: list[RetrievalCandidate] = []
        for candidate, raw_score in scored_candidates[:top_k]:
            # 归一化到 [0, 1]
            normalized = (raw_score - min_score) / score_range
            normalized = max(0.0, min(1.0, normalized))

            # 写入 rerank_score（不修改原始候选，创建副本）
            ranked = _copy_with_rerank(candidate, round(normalized, 4))
            results.append(ranked)

        return results


class IdentityReranker(BaseReranker):
    """恒等 Reranker（不做重排序，用于测试和 baseline 对比）。

    不调用任何模型，直接返回原始候选的前 top_k 个。
    """

    name = "identity"

    def rerank(
        self,
        query: str,
        candidates: list[RetrievalCandidate],
        top_k: int = 5,
    ) -> list[RetrievalCandidate]:
        """直接返回前 top_k 候选，不修改分数。"""
        return candidates[:top_k]


def _copy_with_rerank(
    candidate: RetrievalCandidate,
    rerank_score: float,
) -> RetrievalCandidate:
    """创建候选副本并填充 rerank_score。

    不修改原始候选（防御性拷贝），同时更新 score_kind 和 normalized_score
    以反映 rerank 分数为新的排序依据。
    """
    from dochris.rag.schemas import normalize_score

    new_score = normalize_score(rerank_score, "rerank")
    # dataclass 不是 frozen，直接构造新实例
    from dataclasses import fields as dc_fields

    kwargs = {}
    for f in dc_fields(candidate):
        kwargs[f.name] = getattr(candidate, f.name)

    kwargs["rerank_score"] = rerank_score
    kwargs["score_kind"] = "rerank"
    kwargs["normalized_score"] = new_score

    from dochris.rag.schemas import RetrievalCandidate

    return RetrievalCandidate(**kwargs)
