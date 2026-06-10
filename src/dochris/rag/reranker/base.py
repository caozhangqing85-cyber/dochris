"""Reranker 抽象基类

所有 Reranker 实现必须继承 BaseReranker 并实现 rerank() 方法。
Reranker 不替代 retriever，而是在 retrieval 之后对候选进行精排序：
  retriever（粗召回 candidate_k 个）→ reranker（精选 final_k 个）→ LLM context

设计原则：
- 输入输出都是 list[RetrievalCandidate]，不引入新类型
- rerank_score 写入候选的 rerank_score 字段，normalized_score 由调用方更新
- 默认关闭，不影响现有行为
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dochris.rag.schemas import RetrievalCandidate


class BaseReranker(ABC):
    """Reranker 抽象基类。

    子类必须：
    1. 设置 name 属性
    2. 实现 rerank() 方法
    """

    name: str = "base"

    @abstractmethod
    def rerank(
        self,
        query: str,
        candidates: list[RetrievalCandidate],
        top_k: int = 5,
    ) -> list[RetrievalCandidate]:
        """按 query-candidate 相关性重排候选。

        Args:
            query: 用户查询文本
            candidates: 已归一化的检索候选列表
            top_k: 最终返回的候选数量

        Returns:
            重排序后的候选列表（长度 <= top_k），每个候选的
            rerank_score 字段被填充为 [0, 1] 的相关性分数
        """
        ...
