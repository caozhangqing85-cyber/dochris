"""递归字符分块器（token-aware）

借鉴 LangChain RecursiveCharacterTextSplitter 的递归切分思想：
按分隔符优先级递归（段落 > 换行 > 句子 > 空格），尽量保留语义完整性。
只有当某级分隔符切出的块仍超 chunk_size，才用下一级更细的分隔符。

length_function 默认用字符数（中文 1 字符≈1 token，英文约 4 字符≈1 token）。
可通过 length_function 参数注入 tiktoken 等精确 token 计数器。
"""

from __future__ import annotations

from collections.abc import Callable

from dochris.rag.chunking.base import BaseChunker, ChunkMetadata, DocumentChunk

# 默认分隔符优先级：从粗到细
_DEFAULT_SEPARATORS: list[str] = [
    "\n\n",  # 段落
    "\n",  # 行
    "。",  # 中文句号
    "！",  # 中文叹号
    "？",  # 中文问号
    ". ",  # 英文句号
    "! ",
    "? ",
    " ",  # 空格
    "",  # 逐字符（最后兜底）
]


class RecursiveChunker(BaseChunker):
    """token-aware 递归字符分块器。

    Args:
        chunk_size: 目标块大小（由 length_function 度量，默认字符数）
        overlap: 重叠量（同度量）
        separators: 分隔符优先级列表，从粗到细
        length_function: 文本长度度量函数，默认 len
        keep_separator: 是否保留分隔符（保留可减少语义割裂）
    """

    name = "recursive"

    def __init__(
        self,
        chunk_size: int = 800,
        overlap: int = 120,
        *,
        separators: list[str] | None = None,
        length_function: Callable[[str], int] = len,
        keep_separator: bool = True,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError(f"chunk_size 必须为正数，得到 {chunk_size}")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError(f"overlap 必须满足 0 <= overlap < chunk_size，得到 {overlap}")
        self._chunk_size = chunk_size
        self._overlap = overlap
        self._separators = separators if separators is not None else _DEFAULT_SEPARATORS
        self._length = length_function
        self._keep_separator = keep_separator

    def split(
        self,
        text: str,
        metadata: ChunkMetadata,
    ) -> list[DocumentChunk]:
        """递归切分文本，保证每个 chunk 不超过 chunk_size。"""
        if not text:
            return []

        # 递归切分得到片段列表
        splits = self._split_text(text, self._separators)
        # 合并片段到 chunk_size，带 overlap
        merged = self._merge_splits(splits)

        result: list[DocumentChunk] = []
        search_start = 0
        for idx, content in enumerate(merged):
            if not content:
                continue
            # 定位 chunk 在原文中的字符区间
            pos = text.find(content, search_start)
            if pos == -1:
                start_char = search_start
                end_char = min(search_start + self._length(content), len(text))
            else:
                start_char = pos
                end_char = pos + len(content)
                search_start = end_char

            chunk_meta = ChunkMetadata(
                src_id=metadata.src_id,
                title=metadata.title,
                section="",
                start_char=start_char,
                end_char=end_char,
                strategy=self.name,
                extra={"chunk_size": self._chunk_size, "overlap": self._overlap, **metadata.extra},
            )
            result.append(
                DocumentChunk(
                    id=f"{metadata.src_id}_chunk_{idx:04d}",
                    content=content,
                    metadata=chunk_meta,
                )
            )
        return result

    def _split_text(self, text: str, separators: list[str]) -> list[str]:
        """按分隔符优先级递归切分。"""
        final_chunks: list[str] = []

        # 选第一个能切出多段的分隔符
        new_separators: list[str] = []
        chosen_sep: str | None = None
        for i, sep in enumerate(separators):
            if sep == "":
                chosen_sep = sep
                break
            if sep in text:
                chosen_sep = sep
                new_separators = separators[i + 1 :]
                break

        if chosen_sep is None:
            # 无分隔符可用，直接返回原文
            return [text] if text else []

        if chosen_sep == "":
            # 逐字符兜底切分
            return self._split_by_chars(text)

        # 按选定分隔符切分（保留分隔符）
        parts = self._split_with_separator(text, chosen_sep)

        # 对每个超长片段，用下一级分隔符递归切分
        for part in parts:
            if self._length(part) <= self._chunk_size:
                final_chunks.append(part)
            else:
                if new_separators:
                    final_chunks.extend(self._split_text(part, new_separators))
                else:
                    # 已无更细分隔符，按字符兜底
                    final_chunks.extend(self._split_by_chars(part))

        return [c for c in final_chunks if c]

    def _split_with_separator(self, text: str, sep: str) -> list[str]:
        """按分隔符切分，可选保留分隔符。"""
        if not self._keep_separator:
            return [p for p in text.split(sep) if p]

        # 保留分隔符：将分隔符附到前一段末尾
        result: list[str] = []
        parts = text.split(sep)
        for i, part in enumerate(parts):
            if i == 0:
                result.append(part)
            else:
                result.append(sep + part)
        return [p for p in result if p]

    def _split_by_chars(self, text: str) -> list[str]:
        """按 chunk_size 字符切分（无 overlap，overlap 在 merge 阶段处理）。"""
        step = self._chunk_size
        return [text[i : i + step] for i in range(0, len(text), step)]

    def _merge_splits(self, splits: list[str]) -> list[str]:
        """将小片段合并到 chunk_size 以内，带 overlap。

        overlap 通过"回退若干片段"实现，而非按字符回退，
        这样能保证 overlap 边界落在分隔符上。
        """
        if not splits:
            return []

        merged: list[str] = []
        current: list[str] = []
        current_len = 0

        for split in splits:
            split_len = self._length(split)
            # 加入当前片段会超长 → 先收尾当前 chunk
            if current and current_len + split_len > self._chunk_size:
                merged.append("".join(current))
                # overlap：保留尾部若干片段
                overlap_splits: list[str] = []
                overlap_len = 0
                for s in reversed(current):
                    s_len = self._length(s)
                    if overlap_len + s_len > self._overlap:
                        break
                    overlap_splits.insert(0, s)
                    overlap_len += s_len
                current = overlap_splits
                current_len = overlap_len

            current.append(split)
            current_len += split_len

        if current:
            merged.append("".join(current))

        return merged
