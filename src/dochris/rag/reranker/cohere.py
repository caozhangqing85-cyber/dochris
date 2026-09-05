"""Cohere Rerank API reranker。

通过 Cohere Rerank REST API（https://api.cohere.com/v1/rerank）对候选做精排，
使用 `cohere` 包（懒加载，未安装时报 ImportError 由调用方降级）。

配置约定（与 settings 对齐，RAG-08 收敛）：
- provider 名：``cohere``
- 模型：``rerank-multilingual-v3.0``（默认）或 ``rerank-v3.5``
- 密钥：环境变量 ``COHERE_API_KEY``
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from dochris.rag.reranker.base import BaseReranker

if TYPE_CHECKING:
    from dochris.rag.schemas import RetrievalCandidate

logger = logging.getLogger(__name__)

DEFAULT_COHERE_MODEL = "rerank-multilingual-v3.0"


class CohereReranker(BaseReranker):
    """Cohere Rerank API 精排。"""

    name = "cohere"

    def __init__(
        self,
        model_name: str = DEFAULT_COHERE_MODEL,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.model_name = model_name
        self.api_key = api_key or os.environ.get("COHERE_API_KEY", "")
        self.timeout = timeout
        if not self.api_key:
            raise ValueError("CohereReranker 需要 COHERE_API_KEY（环境变量）或显式传入 api_key")

    def _rerank_response(
        self, query: str, documents: list[str], top_k: int
    ) -> list[dict[str, Any]]:
        """调用 Cohere Rerank API，返回 results 列表。"""
        try:
            import httpx
        except ImportError as e:  # pragma: no cover - openai 依赖已携带 httpx
            raise ImportError("CohereReranker 需要 httpx（pip install httpx）") from e

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                "https://api.cohere.com/v1/rerank",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_name,
                    "query": query,
                    "documents": documents,
                    "top_n": top_k,
                    "return_documents": False,
                },
            )
            resp.raise_for_status()
            payload = resp.json()
        return list(payload.get("results", []))

    def rerank(
        self,
        query: str,
        candidates: list[RetrievalCandidate],
        top_k: int = 5,
    ) -> list[RetrievalCandidate]:
        """按 Cohere 相关性分数重排候选。"""
        if not candidates:
            return []

        documents = [c.text for c in candidates]
        results = self._rerank_response(query, documents, top_k)

        reranked: list[RetrievalCandidate] = []
        for item in results:
            index = int(item.get("index", -1))
            if index < 0 or index >= len(candidates):
                continue
            candidate = candidates[index]
            candidate.rerank_score = float(item.get("relevance_score", 0.0))
            candidate.normalized_score = min(1.0, max(0.0, candidate.rerank_score))
            reranked.append(candidate)

        reranked.sort(
            key=lambda c: c.rerank_score if c.rerank_score is not None else 0.0, reverse=True
        )
        logger.info(
            "Cohere 精排完成: %d → %d 候选 (model=%s)",
            len(candidates),
            len(reranked),
            self.model_name,
        )
        return reranked[:top_k]
