"""文档分块抽象层

定义统一的分块策略接口，所有 chunker（structure/recursive/semantic）
实现 BaseChunker，由 factory 按配置创建。

设计要点：
- ChunkMetadata 同时承载输入字段（src_id/title/section，调用方传入）
  和输出字段（start_char/end_char，split() 填充），便于 chunk 定位与回溯。
- DocumentChunk.id 由调用方（indexer）生成，保证与 manifest/src_id 体系对齐。
- 复用项目现有 structure_aware_split()，不重写结构感知逻辑。

用法：
    from dochris.rag.chunking import create_chunker

    chunker = create_chunker("recursive", chunk_size=800, overlap=120)
    chunks = chunker.split(text, ChunkMetadata(src_id="SRC-0001", title="文档标题"))
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChunkMetadata:
    """文本块元数据。

    输入字段（调用方传入）：src_id, title, section, strategy, extra
    输出字段（split() 填充）：start_char, end_char
    """

    src_id: str
    """来源 manifest ID（如 SRC-0001）"""

    title: str = ""
    """文档标题"""

    section: str = ""
    """所属章节（chunker 按标题切分时填充）"""

    start_char: int = 0
    """chunk 在原文中的起始字符位置（split() 填充）"""

    end_char: int = 0
    """chunk 在原文中的结束字符位置（split() 填充）"""

    strategy: str = "structure"
    """分块策略名称"""

    extra: dict[str, Any] = field(default_factory=dict)
    """策略特有或插件扩展的额外元数据"""


@dataclass
class DocumentChunk:
    """用于检索索引的文档块。"""

    id: str
    """chunk 唯一标识（由 indexer 生成，如 SRC-0001_chunk_0001）"""

    content: str
    """chunk 文本内容"""

    metadata: ChunkMetadata
    """chunk 元数据"""


class BaseChunker(ABC):
    """文档分块策略抽象基类。

    子类需实现 split()，返回带完整 metadata（含 start_char/end_char）的 chunk 列表。
    """

    name: str = "base"

    @abstractmethod
    def split(
        self,
        text: str,
        metadata: ChunkMetadata,
    ) -> list[DocumentChunk]:
        """将文档文本切为可索引 chunk。

        Args:
            text: 原始文档全文
            metadata: chunk 元数据模板（src_id/title 等输入字段）

        Returns:
            chunk 列表，每个 chunk 的 metadata 已填充 start_char/end_char
        """
        ...

    def split_simple(
        self,
        text: str,
        src_id: str,
        title: str = "",
    ) -> list[DocumentChunk]:
        """便捷入口：自动构造 ChunkMetadata。

        适用于不需要预置 section/strategy 的简单场景。
        """
        return self.split(text, ChunkMetadata(src_id=src_id, title=title, strategy=self.name))
