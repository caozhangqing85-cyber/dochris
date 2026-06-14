"""结构感知分块器 — 包装现有 structure_aware_split()

复用 core/text_chunker.py 中成熟的 Markdown 标题 / 数字编号 / 语义边界
分块逻辑，补充 chunk 在原文中的字符定位（start_char/end_char），
使其可用于 raw chunk indexing。

不重写结构感知逻辑，仅做适配层。
"""

from __future__ import annotations

from dochris.core.text_chunker import structure_aware_split
from dochris.rag.chunking.base import BaseChunker, ChunkMetadata, DocumentChunk


class StructureChunker(BaseChunker):
    """结构感知分块器（默认策略）。

    优先按 Markdown 标题切分，回退到数字编号、再到规则式语义边界。
    与 core/text_chunker.structure_aware_split 行为一致。
    """

    name = "structure"

    def __init__(self, chunk_size: int = 4000, overlap: int = 200) -> None:
        self._chunk_size = chunk_size
        self._overlap = overlap

    def split(
        self,
        text: str,
        metadata: ChunkMetadata,
    ) -> list[DocumentChunk]:
        """按文档结构切分，并定位每个 chunk 在原文中的字符区间。"""
        raw_chunks = structure_aware_split(text, self._chunk_size, self._overlap)

        result: list[DocumentChunk] = []
        search_start = 0
        for idx, raw in enumerate(raw_chunks):
            content = raw.content
            # 在原文中查找 chunk 内容的位置（支持重叠 chunk 的递进查找）
            pos = text.find(content, search_start)
            if pos == -1:
                # 容错：find 失败时从头查一次（罕见，如内容被规范化）
                pos = text.find(content)
            if pos == -1:
                # 仍找不到：退化为区间不重叠
                start_char = search_start
                end_char = search_start + len(content)
            else:
                start_char = pos
                end_char = pos + len(content)
                search_start = end_char  # 下一个 chunk 从这里往后查

            chunk_meta = ChunkMetadata(
                src_id=metadata.src_id,
                title=metadata.title,
                section=raw.title or "",
                start_char=start_char,
                end_char=end_char,
                strategy=self.name,
                extra={"level": raw.level, "index": raw.index, **metadata.extra},
            )
            result.append(
                DocumentChunk(
                    id=f"{metadata.src_id}_chunk_{idx:04d}",
                    content=content,
                    metadata=chunk_meta,
                )
            )
        return result
