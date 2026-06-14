"""LEANN 向量存储实现

LEANN (Low-storage Embedding-based ANN) 是一种存储高效的向量索引，
通过图结构选择性重计算实现 97% 存储节省，适合个人设备本地部署。

安装: pip install leann-vector
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .base import BaseVectorStore

logger = logging.getLogger(__name__)


class LeannStore(BaseVectorStore):
    """LEANN 向量存储（超低存储占用的本地向量库）

    使用 LEANN 的 HNSW 后端和选择性重计算，
    相比传统向量库节省 97% 存储空间。

    环境变量:
        LEANN_INDEX_DIR: 索引存储目录，默认为 workspace/data/leann_indexes
    """

    name = "leann"

    def __init__(
        self,
        index_dir: str | Path | None = None,
        embedding_model: str = "BAAI/bge-small-zh-v1.5",
        backend_name: str = "hnsw",
        graph_degree: int = 32,
        build_complexity: int = 64,
        search_complexity: int = 32,
        recompute: bool = True,
        **kwargs: Any,
    ) -> None:
        self._index_dir = Path(index_dir) if index_dir else None
        self._embedding_model = embedding_model
        self._backend_name = backend_name
        self._graph_degree = graph_degree
        self._build_complexity = build_complexity
        self._search_complexity = search_complexity
        self._recompute = recompute
        # collection_name -> LeannSearcher
        self._searchers: dict[str, Any] = {}
        # 跟踪每个 collection 的文档 ID
        self._doc_registry: dict[str, dict[str, str]] = {}

    def _get_index_dir(self) -> Path:
        if self._index_dir:
            d = self._index_dir
        else:
            from dochris.settings import get_settings

            d = get_settings().data_dir / "leann_indexes"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _collection_dir(self, collection: str) -> Path:
        d = self._get_index_dir() / collection
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _load_registry(self, collection: str) -> dict[str, str]:
        if collection in self._doc_registry:
            return self._doc_registry[collection]
        reg_file = self._collection_dir(collection) / "_registry.json"
        if reg_file.exists():
            try:
                self._doc_registry[collection] = json.loads(reg_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._doc_registry[collection] = {}
        else:
            self._doc_registry[collection] = {}
        return self._doc_registry[collection]

    def _save_registry(self, collection: str) -> None:
        reg = self._doc_registry.get(collection, {})
        reg_file = self._collection_dir(collection) / "_registry.json"
        reg_file.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_documents(
        self,
        collection: str,
        documents: list[str],
        ids: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """添加文档到 LEANN 索引

        LEANN 使用 builder 模式构建索引，每次 add_documents 会重建整个集合索引。
        """
        if len(documents) != len(ids):
            raise ValueError(f"documents ({len(documents)}) and ids ({len(ids)}) length mismatch")

        try:
            from leann.api import LeannBuilder
        except ImportError as e:
            raise ImportError("leann-vector not installed. Run: pip install leann-vector") from e

        col_dir = self._collection_dir(collection)

        # 加载已有注册表，合并新文档
        registry = self._load_registry(collection)
        for i, doc_id in enumerate(ids):
            registry[doc_id] = documents[i]
        self._doc_registry[collection] = registry
        self._save_registry(collection)

        # 重建索引
        all_chunks = list(registry.values())
        builder = LeannBuilder(
            backend_name=self._backend_name,
            embedding_mode="sentence-transformers",
            embedding_model=self._embedding_model,
            graph_degree=self._graph_degree,
            build_complexity=self._build_complexity,
        )
        builder.build_index(str(col_dir), all_chunks)

        # 清除缓存的 searcher
        self._searchers.pop(collection, None)
        logger.info(f"LEANN: built index for '{collection}' with {len(all_chunks)} documents")

    def query(
        self,
        collection: str,
        query_text: str,
        n_results: int = 5,
        where: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """使用 LEANN 搜索相似文档"""
        try:
            from leann import LeannSearcher
        except ImportError:
            logger.warning("leann-vector not installed")
            return []

        col_dir = self._collection_dir(collection)
        if not (col_dir / "meta.json").exists():
            return []

        # 获取或创建 searcher
        if collection not in self._searchers:
            try:
                self._searchers[collection] = LeannSearcher(str(col_dir))
            except Exception as e:
                logger.warning(f"LEANN: failed to create searcher for '{collection}': {e}")
                return []

        searcher = self._searchers[collection]
        try:
            results = searcher.search(
                query_text,
                top_k=n_results,
                recompute_embeddings=self._recompute,
                search_complexity=self._search_complexity,
            )
        except Exception as e:
            logger.warning(f"LEANN search failed for '{collection}': {e}")
            return []

        # 转换为统一格式
        output: list[dict[str, Any]] = []
        registry = self._load_registry(collection)
        # 构建反向映射 text→doc_id，用于正确还原 LEANN 返回结果的 doc_id。
        # 不能用 registry.keys() 的位置索引（HNSW 构建可能重排 chunk 顺序导致错位）
        text_to_id: dict[str, str] = {}
        for doc_id, doc_text in registry.items():
            # 去重场景下 text 应唯一；若重复，后写入的 doc_id 覆盖（保守取最新）
            text_to_id[doc_text] = doc_id

        # LEANN 返回的结果格式可能不同，做兼容处理
        if isinstance(results, list):
            for item in results[:n_results]:
                if isinstance(item, dict):
                    text = item.get("text", item.get("document", ""))
                    score = item.get("score", item.get("distance", 0))
                    doc_id = item.get("id", "") or text_to_id.get(text, "")
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    text = str(item[0])
                    score = float(item[1])
                    doc_id = text_to_id.get(text, "")
                else:
                    continue
                output.append(
                    {
                        "id": doc_id,
                        "document": text,
                        "metadata": {},
                        "distance": score,
                    }
                )
        elif isinstance(results, dict):
            texts = results.get("texts", results.get("documents", []))
            scores = results.get("scores", results.get("distances", []))
            for i, text in enumerate(texts[:n_results]):
                score = scores[i] if i < len(scores) else 0
                # 用 text 反查 doc_id，而非位置索引（修正 HNSW 重排后的错位）
                doc_id = text_to_id.get(text, f"doc-{i}")
                output.append(
                    {
                        "id": doc_id,
                        "document": text,
                        "metadata": {},
                        "distance": float(score),
                    }
                )

        return output

    def delete(self, collection: str, ids: list[str]) -> None:
        """从注册表中移除文档并重建索引"""
        registry = self._load_registry(collection)
        for doc_id in ids:
            registry.pop(doc_id, None)
        self._doc_registry[collection] = registry
        self._save_registry(collection)

        if registry:
            # 重建索引（LEANN 不支持增量删除）
            all_chunks = list(registry.values())
            try:
                from leann.api import LeannBuilder

                col_dir = self._collection_dir(collection)
                builder = LeannBuilder(
                    backend_name=self._backend_name,
                    embedding_mode="sentence-transformers",
                    embedding_model=self._embedding_model,
                    graph_degree=self._graph_degree,
                    build_complexity=self._build_complexity,
                )
                builder.build_index(str(col_dir), all_chunks)
                self._searchers.pop(collection, None)
            except ImportError:
                pass

    def list_collections(self) -> list[str]:
        """列出所有 LEANN 集合"""
        index_dir = self._get_index_dir()
        collections = []
        for d in index_dir.iterdir():
            if d.is_dir() and (d / "meta.json").exists():
                collections.append(d.name)
        return collections

    def get_collection_count(self, collection: str) -> int:
        """获取集合中的文档数量"""
        registry = self._load_registry(collection)
        return len(registry)
