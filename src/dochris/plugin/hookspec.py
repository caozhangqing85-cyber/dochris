"""插件 Hook 接口定义

定义插件系统的扩展点（HookSpec），使用 @hookspec 装饰器标记。
插件开发者使用 @hookimpl 装饰器实现对应 hook。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Hook 规范注册表
_HOOK_SPECS: dict[str, HookSpec] = {}


class HookSpec:
    """Hook 规范描述

    Attributes:
        name: Hook 名称
        firstresult: 是否只返回第一个非 None 结果
        historic: 是否调用历史中所有注册的 impl
    """

    __slots__ = ("name", "firstresult", "historic")

    def __init__(
        self,
        name: str,
        firstresult: bool = False,
        historic: bool = False,
    ) -> None:
        self.name = name
        self.firstresult = firstresult
        self.historic = historic

    def __repr__(self) -> str:
        return f"HookSpec({self.name!r}, firstresult={self.firstresult})"


def hookspec(func: Callable) -> Callable:
    """标记函数为 hookspec（插件接口定义）

    Args:
        func: 被标记的函数

    Returns:
        原函数（带有 _is_hookspec 属性）

    Examples:
        >>> @hookspec
        ... def my_hook(arg: str) -> str | None:
        ...     \"\"\"Hook 文档\"\"\"
        ...     pass
    """
    spec = HookSpec(func.__name__)
    _HOOK_SPECS[func.__name__] = spec
    func._is_hookspec = True  # type: ignore[attr-defined]
    return func


def hookimpl(func: Callable) -> Callable:
    """标记函数为 hookimpl（插件实现）

    Args:
        func: 被标记的函数

    Returns:
        原函数（带有 _is_hookimpl 属性）

    Examples:
        >>> @hookimpl
        ... def my_hook(arg: str) -> str | None:
        ...     return f"processed: {arg}"
    """
    func._is_hookimpl = True  # type: ignore[attr-defined]
    return func


def get_hookspec(name: str) -> HookSpec | None:
    """获取指定名称的 HookSpec

    Args:
        name: Hook 名称

    Returns:
        HookSpec 实例，不存在返回 None
    """
    return _HOOK_SPECS.get(name)


def list_hookspecs() -> list[str]:
    """列出所有已注册的 HookSpec 名称

    Returns:
        HookSpec 名称列表
    """
    return list(_HOOK_SPECS.keys())


# ============================================================
# 6 个扩展点定义
# ============================================================


@hookspec
def ingest_parser(file_path: str) -> str | None:
    """自定义文件解析器

    允许插件为特定文件类型提供自定义文本提取逻辑。
    如果插件返回 None，系统将使用默认解析器。

    Args:
        file_path: 文件路径

    Returns:
        提取的文本，None 表示不处理此文件（使用默认解析器）

    Examples:
        >>> @hookimpl
        ... def ingest_parser(file_path: str) -> str | None:
        ...     if file_path.endswith(".epub"):
        ...         return extract_epub_text(file_path)
        ...     return None
    """
    ...


@hookspec
def pre_compile(text: str, metadata: dict[str, Any]) -> tuple[str, dict[str, Any]]:  # type: ignore[empty-body]
    """编译前处理

    在 LLM 编译之前对文本和元数据进行预处理。
    可用于文本清洗、格式转换、元数据增强等。

    Args:
        text: 待编译文本
        metadata: 文件元数据

    Returns:
        (处理后的文本, 更新后的元数据)

    Examples:
        >>> @hookimpl
        ... def pre_compile(text: str, metadata: dict) -> tuple[str, dict]:
        ...     # 清理特殊字符
        ...     clean_text = text.replace("\\x00", "")
        ...     # 添加来源标记
        ...     metadata["processed"] = True
        ...     return clean_text, metadata
    """
    ...


@hookspec
def post_compile(src_id: str, result: dict[str, Any]) -> None:
    """编译后处理

    在编译完成后执行的后处理操作。
    可用于发送通知、更新索引、触发其他流程等。

    Args:
        src_id: 文件 ID（如 SRC-0001）
        result: 编译结果字典

    Examples:
        >>> @hookimpl
        ... def post_compile(src_id: str, result: dict) -> None:
        ...     if result.get("status") == "compiled":
        ...         send_notification(f"编译完成: {src_id}")
    """
    ...


@hookspec
def quality_score(text: str, metadata: dict[str, Any] | None = None) -> float | None:
    """自定义质量评分

    允许插件提供自定义的质量评分算法。
    返回 None 表示使用默认评分。

    Args:
        text: 编译后文本
        metadata: 文件元数据（可选）

    Returns:
        0-100 的分数，None 表示使用默认评分

    Examples:
        >>> @hookimpl
        ... def quality_score(text: str, metadata: dict | None) -> float | None:
        ...     # 自定义评分逻辑
        ...     score = len(text) / 100  # 简单示例
        ...     return min(score, 100) if score > 0 else None
    """
    ...


@hookspec
def pre_query(query: str) -> str:  # type: ignore[empty-body]
    """查询前处理

    在执行查询前对查询字符串进行预处理。
    可用于查询扩展、拼写纠正、意图识别等。

    Args:
        query: 原始查询

    Returns:
        处理后的查询

    Examples:
        >>> @hookimpl
        ... def pre_query(query: str) -> str:
        ...     # 展开缩写
        ...     return query.replace("kb", "knowledge base")
    """
    ...


@hookspec
def post_query(query: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:  # type: ignore[empty-body]
    """查询后处理（结果重排/过滤）

    在查询结果返回前进行后处理。
    可用于结果重排、过滤、聚合等。

    Args:
        query: 查询文本
        results: 查询结果列表

    Returns:
        处理后的结果列表

    Examples:
        >>> @hookimpl
        ... def post_query(query: str, results: list[dict]) -> list[dict]:
        ...     # 过滤低分结果
        ...     return [r for r in results if r.get("score", 0) > 0.5]
    """
    ...
