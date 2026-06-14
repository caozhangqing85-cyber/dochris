"""文档分块模块

提供统一的分块策略接口，支持 structure / recursive / semantic 三种策略。
由 factory 按配置创建 BaseChunker 实例。

策略说明：
- structure: 结构感知分块（Markdown 标题 > 数字编号 > 规则式语义边界），默认
- recursive: token-aware 递归分块（借鉴 LangChain RecursiveCharacterTextSplitter）
- semantic: 基于 embedding 相邻距离断点的语义分块（实验性，需 embedding 模型）
"""

from dochris.rag.chunking.base import BaseChunker, ChunkMetadata, DocumentChunk
from dochris.rag.chunking.factory import create_chunker
from dochris.rag.chunking.recursive import RecursiveChunker
from dochris.rag.chunking.semantic import SemanticChunker
from dochris.rag.chunking.structure import StructureChunker

__all__ = [
    "BaseChunker",
    "ChunkMetadata",
    "DocumentChunk",
    "RecursiveChunker",
    "SemanticChunker",
    "StructureChunker",
    "create_chunker",
]
