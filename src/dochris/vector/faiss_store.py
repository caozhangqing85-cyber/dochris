"""FAISS 向量存储实现（轻量级，无需服务）

使用 sentence-transformers 生成嵌入，FAISS 进行向量检索。
数据持久化为 JSON 元数据 + FAISS 索引文件。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .base import BaseVectorStore

logger = logging.getLogger(__name__)


class FAISSStore(BaseVectorStore):
    """FAISS 向量存储（本地文件，无需服务进程）

    使用 sentence-transformers 生成嵌入，FAISS IndexFlatL2 进行向量检索。
    数据持久化为：
    - index.faiss: FAISS 索引文件
    - metadata.json: 文档内容和元数据

    Examples:
        >>> store = FAISSStore(persist_directory="./faiss_data")
        >>> store.add_documents("my_collection", ["doc1", "doc2"], ["id1", "id2"])
        >>> results = store.query("my_collection", "search query", n_results=5)
    """

    name = "faiss"

    def __init__(
        self,
        persist_directory: str | Path | None = None,
        embedding_model: str = "all-MiniLM-L6-v2",
        **kwargs: Any,
    ) -> None:
        """初始化 FAISS 存储

        Args:
            persist_directory: 持久化目录路径
            embedding_model: sentence-transformers 模型名称
            **kwargs: 其他参数（当前未使用）
        """
        self._persist_directory = (
            Path(persist_directory) if persist_directory else Path("./faiss_data")
        )
        self._embedding_model_name = embedding_model
        self._model: Any = None
        self._indexes: dict[str, Any] = {}  # collection -> faiss.Index
        self._documents: dict[str, dict[str, str]] = {}  # collection -> {id: document}
        self._metadatas: dict[str, dict[str, dict]] = {}  # collection -> {id: metadata}

    def _get_model(self) -> Any:
        """获取或创建嵌入模型

        Returns:
            sentence-transformers 模型

        Raises:
            ImportError: sentence-transformers 未安装
        """
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise ImportError(
                    "sentence-transformers not installed. Run: pip install sentence-transformers"
                ) from e

            self._model = SentenceTransformer(self._embedding_model_name)
            logger.debug(f"Loaded SentenceTransformer model: {self._embedding_model_name}")

        return self._model

    def _get_index_path(self, collection: str) -> Path:
        """获取集合的索引目录路径

        Args:
            collection: 集合名称

        Returns:
            索引目录路径
        """
        return self._persist_directory / collection

    def _load_collection(self, collection: str) -> None:
        """从磁盘加载集合数据

        Args:
            collection: 集合名称
        """
        if collection in self._indexes:
            return

        index_dir = self._get_index_path(collection)
        if not index_dir.exists():
            self._indexes[collection] = None
            self._documents[collection] = {}
            self._metadatas[collection] = {}
            return

        try:
            import faiss  # noqa: F401

            index_path = index_dir / "index.faiss"
            if index_path.exists():
                self._indexes[collection] = faiss.read_index(str(index_path))
            else:
                self._indexes[collection] = None

            meta_path = index_dir / "metadata.json"
            if meta_path.exists():
                with open(meta_path, encoding="utf-8") as f:
                    data = json.load(f)
                self._documents[collection] = data.get("documents", {})
                self._metadatas[collection] = data.get("metadatas", {})
            else:
                self._documents[collection] = {}
                self._metadatas[collection] = {}

            logger.debug(f"Loaded FAISS index for collection '{collection}'")

        except ImportError:
            logger.warning("faiss not installed")
            self._indexes[collection] = None
            self._documents[collection] = {}
            self._metadatas[collection] = {}
        except Exception as e:
            logger.warning(f"Failed to load FAISS index for '{collection}': {e}")
            self._indexes[collection] = None
            self._documents[collection] = {}
            self._metadatas[collection] = {}

    def _save_collection(self, collection: str) -> None:
        """保存集合数据到磁盘

        Args:
            collection: 集合名称
        """
        try:
            import faiss  # noqa: F401
        except ImportError:
            return

        index_dir = self._get_index_path(collection)
        index_dir.mkdir(parents=True, exist_ok=True)

        # 保存 FAISS 索引
        index = self._indexes.get(collection)
        if index is not None and index.ntotal > 0:
            faiss.write_index(index, str(index_dir / "index.faiss"))

        # 保存元数据
        with open(index_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "documents": self._documents.get(collection, {}),
                    "metadatas": self._metadatas.get(collection, {}),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        logger.debug(f"Saved FAISS index for collection '{collection}'")

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
            ImportError: faiss 未安装
            ValueError: 参数长度不匹配
        """
        try:
            import faiss  # noqa: F401
        except ImportError as e:
            raise ImportError("faiss not installed. Run: pip install faiss-cpu") from e

        if len(documents) != len(ids):
            raise ValueError(f"documents ({len(documents)}) and ids ({len(ids)}) length mismatch")

        model = self._get_model()
        self._load_collection(collection)

        # 生成嵌入
        embeddings = model.encode(documents).astype("float32")
        dimension = embeddings.shape[1]

        # 获取或创建索引
        index = self._indexes.get(collection)
        if index is None:
            index = faiss.IndexFlatL2(dimension)

        # 添加向量
        index.add(embeddings)
        self._indexes[collection] = index

        # 保存文档和元数据
        if metadatas is None:
            metadatas = [{}] * len(documents)
        elif len(metadatas) != len(documents):
            raise ValueError(
                f"metadatas ({len(metadatas)}) and documents ({len(documents)}) length mismatch"
            )

        for i, doc_id in enumerate(ids):
            self._documents[collection][doc_id] = documents[i]
            self._metadatas[collection][doc_id] = metadatas[i]

        # 持久化
        self._save_collection(collection)
        logger.debug(f"Added {len(documents)} documents to FAISS collection '{collection}'")

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
            **kwargs: 其他参数（当前未使用）

        Returns:
            结果列表
        """
        try:
            import faiss  # noqa: F401
        except ImportError as e:
            raise ImportError("faiss not installed. Run: pip install faiss-cpu") from e

        model = self._get_model()
        self._load_collection(collection)

        index = self._indexes.get(collection)
        if index is None or index.ntotal == 0:
            return []

        # 生成查询向量
        query_embedding = model.encode([query_text]).astype("float32")

        # 搜索
        k = min(n_results, index.ntotal)
        distances, indices = index.search(query_embedding, k)

        # 构建结果
        results: list[dict[str, Any]] = []
        docs = self._documents.get(collection, {})
        metas = self._metadatas.get(collection, {})

        for i, idx in enumerate(indices[0]):
            if idx < 0:
                continue

            # FAISS 返回内部索引，映射到文档 ID
            doc_keys = list(docs.keys())
            if idx >= len(doc_keys):
                continue

            doc_id = doc_keys[idx]

            # 应用 where 过滤
            if where and doc_id in metas:
                match = all(metas[doc_id].get(k) == v for k, v in where.items())
                if not match:
                    continue

            results.append(
                {
                    "id": doc_id,
                    "document": docs[doc_id],
                    "metadata": metas.get(doc_id, {}),
                    "distance": float(distances[0][i]),
                }
            )

        return results

    def delete(self, collection: str, ids: list[str]) -> None:
        """删除文档

        Note:
            FAISS 不支持高效删除，需要重建索引。

        Args:
            collection: 集合名称
            ids: 要删除的文档 ID 列表
        """
        logger.warning(
            "FAISS does not support efficient deletion. Rebuilding index for '%s'...",
            collection,
        )
        self._load_collection(collection)

        docs = self._documents.get(collection, {})
        metas = self._metadatas.get(collection, {})

        # 收集保留的文档
        remaining_docs = []
        remaining_ids = []
        remaining_metas = []

        ids_to_delete = set(ids)
        for doc_id, doc in docs.items():
            if doc_id not in ids_to_delete:
                remaining_docs.append(doc)
                remaining_ids.append(doc_id)
                remaining_metas.append(metas.get(doc_id, {}))

        # 重建索引
        self._documents[collection] = {}
        self._metadatas[collection] = {}
        self._indexes[collection] = None

        if remaining_docs:
            self.add_documents(collection, remaining_docs, remaining_ids, remaining_metas)

        logger.debug(f"Deleted {len(ids)} documents from FAISS collection '{collection}'")

    def list_collections(self) -> list[str]:
        """列出所有集合

        Returns:
            集合名称列表
        """
        if not self._persist_directory.exists():
            return []

        return [
            d.name
            for d in self._persist_directory.iterdir()
            if d.is_dir() and (d / "index.faiss").exists()
        ]

    def get_collection_count(self, collection: str) -> int:
        """获取集合中文档数量

        Args:
            collection: 集合名称

        Returns:
            文档数量
        """
        self._load_collection(collection)
        index = self._indexes.get(collection)
        return index.ntotal if index is not None else 0

    def close(self) -> None:
        """清理资源"""
        self._indexes.clear()
        self._documents.clear()
        self._metadatas.clear()
        self._model = None
