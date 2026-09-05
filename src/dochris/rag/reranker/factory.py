"""Reranker 工厂 — 根据 provider 名称创建 Reranker 实例

支持的 provider：
- cross_encoder（默认）：基于 sentence_transformers.CrossEncoder
- bge：CrossEncoder 的别名（BAAI/bge-reranker-base 本质是 CrossEncoder）
- cohere：Cohere Rerank API（需要 COHERE_API_KEY）
- identity：不做重排序，用于测试和 baseline 对比

用法：
    reranker = create_reranker("cross_encoder", model_name="BAAI/bge-reranker-base")
    reranked = reranker.rerank(query, candidates, top_k=5)
"""

from __future__ import annotations

import logging
import os

from dochris.rag.reranker.base import BaseReranker
from dochris.rag.reranker.cohere import CohereReranker
from dochris.rag.reranker.cross_encoder import CrossEncoderReranker, IdentityReranker

logger = logging.getLogger(__name__)

# provider 名称 → Reranker 类
_PROVIDERS: dict[str, type[BaseReranker]] = {
    "cross_encoder": CrossEncoderReranker,
    "bge": CrossEncoderReranker,
    "cohere": CohereReranker,
    "identity": IdentityReranker,
}


def create_reranker(
    provider: str = "bge",
    model_name: str = "BAAI/bge-reranker-base",
    max_length: int = 512,
    device: str = "auto",
) -> BaseReranker:
    """创建 Reranker 实例。

    Args:
        provider: Reranker 提供商名称（cross_encoder / bge / cohere / identity）
        model_name: CrossEncoder 模型名称；cohere provider 下为 Cohere
            rerank 模型名（默认 rerank-multilingual-v3.0）
        max_length: 输入最大 token 长度（仅 CrossEncoder 使用）
        device: 推理设备（auto/cpu/cuda/mps，仅 CrossEncoder 使用）

    Returns:
        BaseReranker 实例

    Raises:
        ValueError: 不支持的 provider
    """
    provider = provider.lower().strip()

    if provider not in _PROVIDERS:
        available = ", ".join(sorted(_PROVIDERS.keys()))
        raise ValueError(f"不支持的 Reranker provider: '{provider}'。可选值: {available}")

    cls = _PROVIDERS[provider]

    # IdentityReranker 不需要模型参数
    if cls is IdentityReranker:
        logger.info("创建 IdentityReranker（不做重排序）")
        return IdentityReranker()

    # Cohere：走 Rerank API，不需要本地模型
    if cls is CohereReranker:
        if not os.environ.get("COHERE_API_KEY"):
            raise ValueError("RERANKER_PROVIDER=cohere 需要设置 COHERE_API_KEY 环境变量")
        resolved_model = (
            model_name if model_name and "/" not in model_name else "rerank-multilingual-v3.0"
        )
        logger.info("创建 CohereReranker: model=%s", resolved_model)
        return CohereReranker(model_name=resolved_model)

    # CrossEncoder 系列
    logger.info("创建 CrossEncoderReranker: provider=%s, model=%s", provider, model_name)
    return CrossEncoderReranker(
        model_name=model_name,
        max_length=max_length,
        device=device,
    )
