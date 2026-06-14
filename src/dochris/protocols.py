"""Dochris 接口协议"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """LLM 提供商接口"""

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 4000,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str: ...

    async def generate_with_messages(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 4000,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str: ...

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 4000,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> AsyncIterator[str]: ...

    async def close(self) -> None: ...


@runtime_checkable
class VectorStore(Protocol):
    """向量数据库接口

    与 BaseVectorStore ABC 保持一致。Protocol 用于鸭子类型检查（isinstance），
    ABC 用于继承实现。两者方法签名和返回类型必须对齐。
    """

    def add_documents(
        self,
        collection: str,
        documents: list[str],
        ids: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None: ...

    def query(
        self,
        collection: str,
        query_text: str,
        n_results: int = 5,
        where: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]: ...

    def delete(self, collection: str, ids: list[str]) -> None: ...

    def list_collections(self) -> list[str]: ...

    def get_collection_count(self, collection: str) -> int: ...


@runtime_checkable
class FileParser(Protocol):
    """文件解析器接口"""

    def supported_extensions(self) -> list[str]: ...

    def parse(self, file_path: str, **kwargs: Any) -> str: ...


@runtime_checkable
class QualityScorer(Protocol):
    """质量评分器接口"""

    def score(self, text: str, metadata: dict[str, Any] | None = None) -> float: ...
