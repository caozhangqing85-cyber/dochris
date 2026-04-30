"""向量数据库抽象层

提供统一的向量存储接口，支持多种后端：
- ChromaDB: 默认，持久化到本地文件
- FAISS: 轻量级，无需服务进程
"""

from dochris.vector.base import BaseVectorStore
from dochris.vector.chromadb_store import ChromaDBStore

__all__ = ["BaseVectorStore", "ChromaDBStore", "get_store", "STORES"]

# 向量存储注册表
STORES: dict[str, type[BaseVectorStore]] = {
    "chromadb": ChromaDBStore,
}


def _try_register_faiss() -> None:
    """尝试注册 FAISS store（可选依赖）"""
    try:
        from dochris.vector.faiss_store import FAISSStore

        STORES["faiss"] = FAISSStore
        __all__.append("FAISSStore")
    except ImportError:
        pass


_try_register_faiss()


def get_store(name: str) -> type[BaseVectorStore]:
    """获取向量存储类

    Args:
        name: 存储类型名称（如 "chromadb", "faiss"）

    Returns:
        向量存储类

    Raises:
        ValueError: 未知的存储类型

    Examples:
        >>> store_cls = get_store("chromadb")
        >>> store = store_cls(persist_directory="./data")
    """
    if name not in STORES:
        available = ", ".join(sorted(STORES.keys()))
        raise ValueError(f"Unknown vector store: {name!r}. Available: {available}")
    return STORES[name]
