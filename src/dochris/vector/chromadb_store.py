"""ChromaDB 向量存储实现

包装 ChromaDB 客户端，提供持久化的向量存储。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .base import BaseVectorStore

logger = logging.getLogger(__name__)


def _build_embedding_function(model_name: str) -> Any:
    """构建嵌入函数，使用本地缓存的 SentenceTransformer 模型

    设置 local_files_only=True 避免向 HuggingFace Hub 发起网络请求，
    防止因 SSL/网络问题导致模型加载超时（sentence_transformers v5+
    即使模型已缓存也会尝试检查 adapter_config.json）。
    """
    from chromadb.utils import embedding_functions

    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=model_name,
        local_files_only=True,
    )


class ChromaDBStore(BaseVectorStore):
    """ChromaDB 向量存储（持久化到本地文件）

    使用 PersistentClient 将数据存储到本地目录，
    支持自动嵌入和向量检索。
    """

    name = "chromadb"

    def __init__(
        self,
        persist_directory: str | Path | None = None,
        embedding_model: str = "BAAI/bge-small-zh-v1.5",
        **kwargs: Any,
    ) -> None:
        self._persist_directory = Path(persist_directory) if persist_directory else None
        self._embedding_model = embedding_model
        self._ef: Any | None = None
        self._client: Any | None = None

    @property
    def embedding_function(self) -> Any:
        if self._ef is None:
            try:
                self._ef = _build_embedding_function(self._embedding_model)
                logger.info(f"ChromaDB embedding: {self._embedding_model}")
            except Exception as e:
                logger.warning(f"Failed to load embedding model {self._embedding_model}: {e}")
                return None
        return self._ef

    def _get_client(self) -> Any:
        """获取或创建 ChromaDB 客户端

        Returns:
            ChromaDB 客户端实例

        Raises:
            ImportError: chromadb 未安装
        """
        if self._client is None:
            try:
                import chromadb
            except ImportError as e:
                raise ImportError("chromadb not installed. Run: pip install chromadb") from e

            if self._persist_directory:
                self._persist_directory.mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(path=str(self._persist_directory))
                logger.debug(f"Created ChromaDB PersistentClient at {self._persist_directory}")
            else:
                self._client = chromadb.Client()
                logger.debug("Created ChromaDB in-memory client")

        return self._client

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
            ids: 文档 ID 列表
            metadatas: 可选的元数据列表

        Raises:
            ValueError: documents 和 ids 长度不匹配
        """
        if len(documents) != len(ids):
            raise ValueError(f"documents ({len(documents)}) and ids ({len(ids)}) length mismatch")

        client = self._get_client()
        ef = self.embedding_function
        col = client.get_or_create_collection(
            name=collection,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )

        # 确保元数据列表长度正确
        if metadatas is None:
            metadatas = [{}] * len(documents)
        elif len(metadatas) != len(documents):
            raise ValueError(
                f"metadatas ({len(metadatas)}) and documents ({len(documents)}) length mismatch"
            )

        col.add(documents=documents, ids=ids, metadatas=metadatas)
        logger.debug(f"Added {len(documents)} documents to collection '{collection}'")

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
            **kwargs: ChromaDB 特定参数（如 n_results）

        Returns:
            结果列表，每个结果包含 id, document, metadata, distance
        """
        client = self._get_client()

        # 尝试获取集合（传入 embedding function 以确保一致）
        try:
            ef = self.embedding_function
            col = client.get_collection(name=collection, embedding_function=ef)
        except Exception as e:
            # 区分集合不存在（正常，debug）和真实错误（warning，便于运维发现）
            err_name = type(e).__name__
            if "collection" in str(e).lower() and "not" in str(e).lower():
                logger.debug(f"Collection '{collection}' not found: {e}")
            else:
                logger.warning(f"Failed to get collection '{collection}' ({err_name}): {e}")
            return []

        # 执行查询
        try:
            results = col.query(
                query_texts=[query_text],
                n_results=n_results,
                where=where,
                **kwargs,
            )
        except Exception as e:
            logger.warning(f"Query failed for collection '{collection}': {e}")
            return []

        # 统一返回格式
        output: list[dict[str, Any]] = []
        if results and results.get("ids") and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                output.append(
                    {
                        "id": doc_id,
                        "document": (
                            results["documents"][0][i] if results.get("documents") else ""
                        ),
                        "metadata": (
                            results["metadatas"][0][i] if results.get("metadatas") else {}
                        ),
                        "distance": (
                            results["distances"][0][i] if results.get("distances") else 0.0
                        ),
                    }
                )

        return output

    def delete(self, collection: str, ids: list[str]) -> None:
        """删除文档

        Args:
            collection: 集合名称
            ids: 要删除的文档 ID 列表
        """
        client = self._get_client()
        try:
            col = client.get_collection(name=collection)
            col.delete(ids=ids)
            logger.debug(f"Deleted {len(ids)} documents from collection '{collection}'")
        except Exception as e:
            logger.debug(f"Collection '{collection}' not found for deletion: {e}")

    def update_metadata(
        self,
        collection: str,
        ids: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """批量更新文档元数据（ChromaDB 原生支持 update）。

        Args:
            collection: 集合名称
            ids: 要更新的文档 ID 列表
            metadatas: 对应的新元数据列表（长度须与 ids 一致）
        """
        if len(ids) != len(metadatas):
            raise ValueError(
                f"ids ({len(ids)}) 和 metadatas ({len(metadatas)}) 长度不匹配"
            )
        client = self._get_client()
        try:
            col = client.get_collection(name=collection)
            col.update(ids=ids, metadatas=metadatas)
            logger.debug(f"Updated metadata for {len(ids)} docs in collection '{collection}'")
        except Exception as e:
            logger.warning(f"更新 collection '{collection}' 元数据失败: {e}")

    def list_collections(self) -> list[str]:
        """列出所有集合

        Returns:
            集合名称列表
        """
        client = self._get_client()
        try:
            return [col.name for col in client.list_collections()]
        except Exception:
            return []

    def get_collection_count(self, collection: str) -> int:
        """获取集合中文档数量

        Args:
            collection: 集合名称

        Returns:
            文档数量，集合不存在时返回 0
        """
        client = self._get_client()
        try:
            col = client.get_collection(name=collection)
            return int(col.count())
        except Exception:
            return 0

    def close(self) -> None:
        """清理资源"""
        self._client = None
