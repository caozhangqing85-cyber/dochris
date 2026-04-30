"""向量数据库抽象基类

定义所有向量存储后端必须实现的接口。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseVectorStore(ABC):
    """向量数据库基类 — 所有向量存储后端必须实现

    设计原则：
    - 统一的接口：所有后端实现相同的方法签名
    - 简单的返回格式：返回列表，便于调用方处理
    - 可选的元数据过滤：通过 where 参数实现
    """

    name: str = "base"
    """存储类型标识符"""

    @abstractmethod
    def add_documents(
        self,
        collection: str,
        documents: list[str],
        ids: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """添加文档到集合

        Args:
            collection: 集合名称
            documents: 文档文本列表
            ids: 文档 ID 列表（必须唯一）
            metadatas: 可选的元数据列表

        Raises:
            ValueError: documents 和 ids 长度不匹配
            Exception: 存储失败时抛出具体异常
        """
        ...

    @abstractmethod
    def query(
        self,
        collection: str,
        query_text: str,
        n_results: int = 5,
        where: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """查询相似文档

        Args:
            collection: 集合名称
            query_text: 查询文本
            n_results: 返回结果数量
            where: 可选的元数据过滤条件
            **kwargs: 其他后端特定参数

        Returns:
            结果列表，每个结果包含：
            - id: 文档 ID
            - document: 文档文本
            - metadata: 元数据字典
            - distance: 相似度距离（越小越相似）
        """
        ...

    @abstractmethod
    def delete(self, collection: str, ids: list[str]) -> None:
        """删除文档

        Args:
            collection: 集合名称
            ids: 要删除的文档 ID 列表

        Note:
            某些后端（如 FAISS）删除效率较低，可能需要重建索引
        """
        ...

    @abstractmethod
    def list_collections(self) -> list[str]:
        """列出所有集合

        Returns:
            集合名称列表
        """
        ...

    @abstractmethod
    def get_collection_count(self, collection: str) -> int:
        """获取集合中文档数量

        Args:
            collection: 集合名称

        Returns:
            文档数量，集合不存在时返回 0
        """
        ...

    def collection_exists(self, collection: str) -> bool:
        """检查集合是否存在

        Args:
            collection: 集合名称

        Returns:
            集合是否存在
        """
        return collection in self.list_collections()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
