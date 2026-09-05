"""LEANN 向量存储实现

LEANN (Low-storage Embedding-based ANN) 是一种存储高效的向量索引，
通过图结构选择性重计算实现 97% 存储节省，适合个人设备本地部署。

安装: pip install 'dochris[leann]'
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
        self._doc_registry: dict[str, dict[str, dict[str, Any]]] = {}

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

    def _index_path(self, collection: str) -> Path:
        """Return the stable basename used by LEANN's sibling index files."""
        return self._collection_dir(collection) / "index"

    def _load_registry(self, collection: str) -> dict[str, dict[str, Any]]:
        if collection in self._doc_registry:
            return self._doc_registry[collection]
        reg_file = self._collection_dir(collection) / "_registry.json"
        if reg_file.exists():
            try:
                raw_registry = json.loads(reg_file.read_text(encoding="utf-8"))
                if not isinstance(raw_registry, dict):
                    raise ValueError("registry root must be an object")
                registry: dict[str, dict[str, Any]] = {}
                for doc_id, raw_entry in raw_registry.items():
                    if isinstance(raw_entry, str):
                        registry[str(doc_id)] = {"text": raw_entry, "metadata": {}}
                        continue
                    if not isinstance(raw_entry, dict):
                        continue
                    raw_metadata = raw_entry.get("metadata", {})
                    metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
                    registry[str(doc_id)] = {
                        "text": str(raw_entry.get("text", "")),
                        "metadata": metadata,
                    }
                self._doc_registry[collection] = registry
            except (json.JSONDecodeError, OSError, ValueError):
                self._doc_registry[collection] = {}
        else:
            self._doc_registry[collection] = {}
        return self._doc_registry[collection]

    def _save_registry(self, collection: str) -> None:
        reg = self._doc_registry.get(collection, {})
        reg_file = self._collection_dir(collection) / "_registry.json"
        reg_file.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")

    def _build_index(self, collection: str, registry: dict[str, dict[str, Any]]) -> None:
        """Build a LEANN 0.3.x index from the persisted registry."""
        try:
            from leann import LeannBuilder
        except ImportError as exc:
            raise ImportError("LEANN not installed. Run: pip install 'dochris[leann]'") from exc

        builder = LeannBuilder(
            backend_name=self._backend_name,
            embedding_mode="sentence-transformers",
            embedding_model=self._embedding_model,
            graph_degree=self._graph_degree,
            build_complexity=self._build_complexity,
        )
        for doc_id, entry in registry.items():
            metadata = dict(entry.get("metadata", {}))
            metadata["id"] = doc_id
            builder.add_text(str(entry.get("text", "")), metadata=metadata)
        builder.build_index(str(self._index_path(collection)))
        self._searchers.pop(collection, None)

    def _remove_index(self, collection: str) -> None:
        """Remove LEANN-generated sibling files for an empty collection."""
        for path in self._collection_dir(collection).glob("index*"):
            if path.is_file():
                path.unlink()
        self._searchers.pop(collection, None)

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
        if metadatas is not None and len(metadatas) != len(documents):
            raise ValueError(
                f"metadatas ({len(metadatas)}) and documents ({len(documents)}) length mismatch"
            )

        # 加载已有注册表，合并新文档
        registry = {
            doc_id: {"text": entry["text"], "metadata": dict(entry.get("metadata", {}))}
            for doc_id, entry in self._load_registry(collection).items()
        }
        for i, doc_id in enumerate(ids):
            metadata = dict(metadatas[i]) if metadatas is not None else {}
            metadata.pop("id", None)
            registry[doc_id] = {"text": documents[i], "metadata": metadata}

        # 先完成构建，再提交注册表，避免失败时留下“注册表已更新、索引未更新”的状态。
        self._build_index(collection, registry)
        self._doc_registry[collection] = registry
        self._save_registry(collection)
        logger.info("LEANN: built index for '%s' with %d documents", collection, len(registry))

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
            logger.warning("LEANN not installed; install the 'dochris[leann]' extra")
            return []

        index_path = self._index_path(collection)
        if not Path(f"{index_path}.meta.json").exists():
            return []

        # 获取或创建 searcher
        if collection not in self._searchers:
            try:
                self._searchers[collection] = LeannSearcher(str(index_path))
            except Exception as e:
                logger.warning(f"LEANN: failed to create searcher for '{collection}': {e}")
                return []

        searcher = self._searchers[collection]
        try:
            search_kwargs: dict[str, Any] = {
                "top_k": n_results,
                "complexity": self._search_complexity,
                # PyPI's leann-core 0.3.4 configures recomputation per search;
                # newer 0.3.x releases retain this argument for compatibility.
                "recompute_embeddings": self._recompute,
            }
            if where is not None:
                search_kwargs["metadata_filters"] = where
            results = searcher.search(query_text, **search_kwargs)
        except Exception as e:
            logger.warning(f"LEANN search failed for '{collection}': {e}")
            return []

        # 转换为统一格式
        output: list[dict[str, Any]] = []
        registry = self._load_registry(collection)
        # 构建反向映射 text→doc_id，用于正确还原 LEANN 返回结果的 doc_id。
        # 不能用 registry.keys() 的位置索引（HNSW 构建可能重排 chunk 顺序导致错位）
        text_to_id: dict[str, str] = {}
        for doc_id, entry in registry.items():
            # 去重场景下 text 应唯一；若重复，后写入的 doc_id 覆盖（保守取最新）
            text_to_id[str(entry.get("text", ""))] = doc_id

        # LEANN 返回的结果格式可能不同，做兼容处理
        if isinstance(results, list):
            for item in results[:n_results]:
                if all(hasattr(item, attr) for attr in ("id", "score", "text", "metadata")):
                    text = str(item.text)
                    score = float(item.score)
                    raw_metadata = item.metadata
                    metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
                    doc_id = str(item.id or metadata.get("id") or text_to_id.get(text, ""))
                elif isinstance(item, dict):
                    text = str(item.get("text", item.get("document", "")))
                    score = float(item.get("score", item.get("distance", 0)) or 0)
                    raw_metadata = item.get("metadata", {})
                    metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
                    doc_id = str(
                        item.get("id", "") or metadata.get("id") or text_to_id.get(text, "")
                    )
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    text = str(item[0])
                    score = float(item[1])
                    doc_id = text_to_id.get(text, "")
                    metadata = {}
                else:
                    continue
                metadata.pop("id", None)
                output.append(
                    {
                        "id": doc_id,
                        "document": text,
                        "metadata": metadata,
                        "distance": score,
                    }
                )
        elif isinstance(results, dict):
            texts = results.get("texts", results.get("documents", []))
            scores = results.get("scores", results.get("distances", []))
            if not isinstance(texts, list):
                texts = []
            if not isinstance(scores, list):
                scores = []
            for i, text in enumerate(texts[:n_results]):
                score = scores[i] if i < len(scores) else 0
                # 用 text 反查 doc_id，而非位置索引（修正 HNSW 重排后的错位）
                text = str(text)
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
        registry = {
            doc_id: {"text": entry["text"], "metadata": dict(entry.get("metadata", {}))}
            for doc_id, entry in registry.items()
        }
        for doc_id in ids:
            registry.pop(doc_id, None)

        if registry:
            # 重建索引（LEANN 不支持增量删除）
            self._build_index(collection, registry)
        else:
            self._remove_index(collection)

        self._doc_registry[collection] = registry
        self._save_registry(collection)

    def list_collections(self) -> list[str]:
        """列出所有 LEANN 集合"""
        index_dir = self._get_index_dir()
        collections = []
        for d in index_dir.iterdir():
            if d.is_dir() and (d / "index.meta.json").exists():
                collections.append(d.name)
        return collections

    def get_collection_count(self, collection: str) -> int:
        """获取集合中的文档数量"""
        registry = self._load_registry(collection)
        return len(registry)
