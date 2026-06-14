"""语义分块器（基于 embedding 相邻距离断点）

参考 LangChain SemanticChunker 和 Chonkie SemanticChunker 的思路：
1. 将文本按句子切分
2. 计算相邻句子的 embedding 余弦距离
3. 距离超过阈值（基于百分位）的位置视为语义断点
4. 断点之间的句子合并为一个 chunk

注意：需 embedding 模型，应复用项目已加载的 embedding function
（如 chromadb_store 内部的 SentenceTransformerEmbeddingFunction），
避免重复加载模型浪费内存。embedding 不可用时降级为 recursive 策略。

属于实验性策略，默认不启用，必须通过 RAG eval 验证收益后才能作为默认。
"""

from __future__ import annotations

import logging
from typing import Any

from dochris.rag.chunking.base import BaseChunker, ChunkMetadata, DocumentChunk

logger = logging.getLogger(__name__)


class SemanticChunker(BaseChunker):
    """基于 embedding 相邻距离断点的语义分块器。

    Args:
        chunk_size: 单个 chunk 的最大字符数（断点合并后仍超长则强制切分）
        overlap: 强制切分时的重叠字符数
        embedding_model: embedding 模型名（默认复用 Settings.embedding_model）
        breakpoint_percentile: 断点距离百分位阈值（如 95 表示取距离前 5% 的位置为断点）
        sentence_size: 句子切分的最小字符数（过滤过短句子）
        embedding_func: 可选，外部注入的 embedding 函数（优先于 embedding_model）
    """

    name = "semantic"

    def __init__(
        self,
        chunk_size: int = 4000,
        overlap: int = 200,
        *,
        embedding_model: str = "BAAI/bge-small-zh-v1.5",
        breakpoint_percentile: float = 95.0,
        sentence_size: int = 20,
        embedding_func: Any | None = None,
    ) -> None:
        if not 0 < breakpoint_percentile <= 100:
            raise ValueError(
                f"breakpoint_percentile 必须在 (0, 100]，得到 {breakpoint_percentile}"
            )
        self._chunk_size = chunk_size
        self._overlap = overlap
        self._embedding_model = embedding_model
        self._breakpoint_percentile = breakpoint_percentile
        self._sentence_size = sentence_size
        self._embedding_func = embedding_func  # 外部注入优先
        self._embedder: Any | None = None

    def _get_embedder(self) -> Any:
        """延迟获取 embedding 函数（复用外部注入或加载 sentence_transformers）。"""
        if self._embedder is not None:
            return self._embedder

        if self._embedding_func is not None:
            self._embedder = self._embedding_func
            return self._embedder

        try:
            from sentence_transformers import SentenceTransformer

            logger.info("加载 semantic chunker embedding 模型: %s", self._embedding_model)
            model = SentenceTransformer(self._embedding_model, local_files_only=True)

            def _embed(texts: list[str]) -> list[list[float]]:
                import numpy as np

                vecs = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
                return [np.asarray(v).tolist() for v in vecs]

            self._embedder = _embed
            return self._embedder
        except (ImportError, OSError, Exception) as e:
            logger.warning(
                "semantic chunker 无法加载 embedding 模型 (%s)，将降级为按句子合并",
                e,
            )
            self._embedder = False  # 标记不可用
            return None

    def split(
        self,
        text: str,
        metadata: ChunkMetadata,
    ) -> list[DocumentChunk]:
        """按语义断点切分。embedding 不可用时降级。"""
        if not text:
            return []

        sentences = self._split_sentences(text)
        if len(sentences) < 2:
            return self._build_chunks([text], text, metadata)

        embedder = self._get_embedder()
        if not embedder:
            # 降级：纯按句子 + chunk_size 合并
            logger.debug("semantic chunker 降级为按句子合并")
            return self._merge_sentences_fallback(sentences, text, metadata)

        # 计算相邻句子 embedding 距离
        try:
            distances = self._compute_adjacent_distances(sentences, embedder)
        except Exception as e:
            logger.warning("semantic chunker embedding 计算失败 (%s)，降级", e)
            return self._merge_sentences_fallback(sentences, text, metadata)

        # 按百分位阈值找断点
        if distances:
            import numpy as np

            threshold = float(np.percentile(distances, self._breakpoint_percentile))
        else:
            threshold = float("inf")

        # 分组：距离超阈值处断开
        groups: list[list[str]] = [[sentences[0]]]
        for i, dist in enumerate(distances):
            if dist > threshold:
                groups.append([sentences[i + 1]])
            else:
                groups[-1].append(sentences[i + 1])

        # 合并每组为 chunk 文本，超长的强制切分
        chunk_texts: list[str] = []
        for group in groups:
            group_text = "".join(group)
            if len(group_text) <= self._chunk_size:
                chunk_texts.append(group_text)
            else:
                # 超长则按 chunk_size 强制切分
                for j in range(0, len(group_text), self._chunk_size - self._overlap):
                    chunk_texts.append(group_text[j : j + self._chunk_size])

        return self._build_chunks(chunk_texts, text, metadata)

    def _split_sentences(self, text: str) -> list[str]:
        """按中英文句号/叹号/问号切分句子，保留标点。"""
        import re

        # 按句末标点切分，保留标点
        parts = re.split(r"(?<=[。！？!?])\s*", text.strip())
        # 过滤过短片段（如标题残留），保留短片段拼接到上一句
        result: list[str] = []
        for p in parts:
            p = p.strip()
            if not p:
                continue
            if len(p) < self._sentence_size and result:
                result[-1] += p
            else:
                result.append(p)
        return result if result else [text]

    def _compute_adjacent_distances(
        self, sentences: list[str], embedder: Any
    ) -> list[float]:
        """计算相邻句子的 embedding 余弦距离（1 - cosine_similarity）。"""
        import numpy as np

        vecs = np.array(embedder(sentences), dtype=np.float64)
        # 归一化（若 embedder 已归一化则无副作用）
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        vecs = vecs / norms

        distances: list[float] = []
        for i in range(len(vecs) - 1):
            cos_sim = float(np.dot(vecs[i], vecs[i + 1]))
            distances.append(1.0 - cos_sim)
        return distances

    def _merge_sentences_fallback(
        self,
        sentences: list[str],
        text: str,
        metadata: ChunkMetadata,
    ) -> list[DocumentChunk]:
        """embedding 不可用时的降级：按 chunk_size 合并句子。"""
        chunk_texts: list[str] = []
        current = ""
        for s in sentences:
            if len(current) + len(s) > self._chunk_size and current:
                chunk_texts.append(current)
                # overlap：保留尾部
                tail = current[-self._overlap :] if self._overlap > 0 else ""
                current = tail + s
            else:
                current += s
        if current:
            chunk_texts.append(current)
        return self._build_chunks(chunk_texts, text, metadata)

    def _build_chunks(
        self,
        chunk_texts: list[str],
        text: str,
        metadata: ChunkMetadata,
    ) -> list[DocumentChunk]:
        """将 chunk 文本列表转为 DocumentChunk，定位字符区间。"""
        result: list[DocumentChunk] = []
        search_start = 0
        for idx, content in enumerate(chunk_texts):
            if not content:
                continue
            pos = text.find(content, search_start)
            if pos == -1:
                start_char = search_start
                end_char = min(search_start + len(content), len(text))
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
                extra={
                    "breakpoint_percentile": self._breakpoint_percentile,
                    "embedding_model": self._embedding_model,
                    **metadata.extra,
                },
            )
            result.append(
                DocumentChunk(
                    id=f"{metadata.src_id}_chunk_{idx:04d}",
                    content=content,
                    metadata=chunk_meta,
                )
            )
        return result
