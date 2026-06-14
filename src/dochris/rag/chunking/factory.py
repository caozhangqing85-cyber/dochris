"""分块策略工厂

按配置名称（structure/recursive/semantic）创建 BaseChunker 实例。
所有 chunker 默认关闭对原文的依赖（semantic 需 embedding），通过显式传参启用。

用法：
    from dochris.rag.chunking import create_chunker

    chunker = create_chunker("structure", chunk_size=4000, overlap=200)
    chunks = chunker.split(text, metadata)
"""

from __future__ import annotations

import logging
from typing import Any

from dochris.rag.chunking.base import BaseChunker, ChunkMetadata, DocumentChunk
from dochris.rag.chunking.recursive import RecursiveChunker
from dochris.rag.chunking.semantic import SemanticChunker
from dochris.rag.chunking.structure import StructureChunker

logger = logging.getLogger(__name__)

# 策略名 → chunker 类
_PROVIDERS: dict[str, type[BaseChunker]] = {
    "structure": StructureChunker,
    "recursive": RecursiveChunker,
    "semantic": SemanticChunker,
}


def create_chunker(
    strategy: str = "structure",
    *,
    chunk_size: int = 4000,
    overlap: int = 200,
    **kwargs: Any,
) -> BaseChunker:
    """创建分块器实例。

    Args:
        strategy: 策略名称（structure/recursive/semantic）
        chunk_size: 目标块大小（字符数或 token 数，视策略而定）
        overlap: 重叠量
        **kwargs: 策略特有参数（如 semantic 的 embedding_model、breakpoint_percentile）

    Returns:
        BaseChunker 实例

    Raises:
        ValueError: 未知策略名
    """
    cls = _PROVIDERS.get(strategy)
    if cls is None:
        available = ", ".join(sorted(_PROVIDERS))
        raise ValueError(
            f"未知分块策略: {strategy!r}，可用策略: {available}。\n"
            "可通过 CHUNK_STRATEGY 环境变量配置。"
        )

    # semantic 策略接受额外的 embedding 相关参数
    if strategy == "semantic":
        return cls(  # type: ignore[call-arg]
            chunk_size=chunk_size,
            overlap=overlap,
            **kwargs,
        )
    return cls(chunk_size=chunk_size, overlap=overlap)


__all__ = [
    "BaseChunker",
    "ChunkMetadata",
    "DocumentChunk",
    "RecursiveChunker",
    "SemanticChunker",
    "StructureChunker",
    "create_chunker",
]
