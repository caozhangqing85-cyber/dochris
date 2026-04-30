#!/usr/bin/env python3
"""
LLM 客户端模块

提供与 LLM API 交互的异步客户端核心功能，支持：
- 多提供商支持（OpenAI 兼容 API、Ollama）
- 结构化摘要生成
- 自动重试机制（429、连接错误、超时）
- 速率限制
- JSON 响应解析（支持 json_repair）
- 内容过滤检测

主要类:
    LLMClient: 异步 LLM 客户端（核心功能）
    SummaryGenerator: 摘要生成器（从 summary_generator.py 导入）
    HierarchicalSummarizer: 分层摘要器（从 hierarchical_summarizer.py 导入）

使用示例:
    client = LLMClient(api_key="xxx", base_url="https://api.example.com")
    result = await client.generate_summary(text, title)
"""

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from openai import AsyncOpenAI
else:
    try:
        from openai import AsyncOpenAI
    except ImportError:
        logging.warning("openai not installed. Please install: pip install openai")
        AsyncOpenAI = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# ============================================================
# 客户端实例追踪与清理（用于资源管理）
# ============================================================

_client_instances: list["LLMClient"] = []


def register_client(client: "LLMClient") -> None:
    """注册 LLMClient 实例，用于程序退出时清理资源"""
    _client_instances.append(client)


def cleanup_all_clients() -> None:
    """清理所有已注册的 LLMClient 实例

    此函数设计为在程序退出时通过 atexit 调用，
    确保所有 LLM 客户端的网络连接被正确关闭。

    注意：这是同步函数（atexit 要求），使用 asyncio.run() 在新循环中运行异步关闭。
    """
    if not _client_instances:
        return

    async def _close_all() -> None:
        """在异步上下文中关闭所有客户端"""
        for client in _client_instances:
            try:
                if hasattr(client, "close"):
                    await client.close()
            except Exception:
                pass
        _client_instances.clear()

    try:
        asyncio.run(_close_all())
    except RuntimeError as e:
        # 事件循环已在运行（非常见情况），尝试在线程池中运行
        logger.debug(f"清理 LLMClient 时事件循环冲突: {e}")
        _client_instances.clear()


class LLMClient:
    """异步 LLM 客户端（核心功能）

    提供基础 API 客户端功能，摘要生成功能委托给 SummaryGenerator。

    支持多种 LLM 提供商（通过 provider 配置）：
    - openai_compat: OpenAI 兼容 API（智谱、DeepSeek、OpenAI 等）
    - ollama: Ollama 本地模型

    Attributes:
        client: AsyncOpenAI 客户端实例（向后兼容）
        provider: LLM 提供商实例
        model: 模型名称
        max_tokens: 最大 token 数
        temperature: 温度参数（0.1 保证稳定输出）
        request_delay: 请求间隔（秒）
        last_request_time: 上次请求时间
        no_think: 是否需要 /no_think 标记（qwen3 模型）
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "glm-5.1",
        max_tokens: int = 40000,
        temperature: float = 0.1,
        request_delay: float = 5.0,
        provider: str | None = None,
    ) -> None:
        """初始化 LLM 客户端

        Args:
            api_key: API 密钥
            base_url: API 基础 URL
            model: 模型名称（默认 glm-5.1）
            max_tokens: 最大生成 token 数（默认 40000）
            temperature: 采样温度（默认 0.1，较低温度保证稳定输出）
            request_delay: 请求间隔秒数（默认 5.0，用于速率限制）
            provider: LLM 提供商类型（None 表示自动检测或使用默认）

        Raises:
            ImportError: openai 包未安装时抛出
        """
        # 确定 provider 类型
        if provider is None:
            # 默认使用 openai_compat
            provider = "openai_compat"

        # 创建提供商实例
        from dochris.llm import get_provider

        provider_class = get_provider(provider)
        self.provider = provider_class(
            api_key=api_key,
            api_base=base_url,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=120,
        )

        # 向后兼容：对于 openai_compat，暴露底层的 AsyncOpenAI 客户端
        if provider == "openai_compat" and hasattr(self.provider, "client"):
            self.client = self.provider.client
        else:
            # 对于其他提供商，创建一个兼容的 client 属性
            # 注意：这不会完全兼容所有用法，但能防止 AttributeError
            if AsyncOpenAI is None:
                raise ImportError("openai package not installed")

            import httpx

            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=120.0,
                http_client=httpx.AsyncClient(
                    limits=httpx.Limits(max_connections=1),
                    timeout=120.0,
                ),
                max_retries=0,
            )

        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.request_delay = request_delay
        self.no_think = model and "qwen3" in model.lower()
        self.last_request_time = 0.0

        # 注册实例以便程序退出时清理资源
        register_client(self)

    def _apply_no_think(self, messages: list) -> list:
        """qwen3 模型需要在 system prompt 末尾加 /no_think"""
        if self.no_think and messages and messages[0].get("role") == "system":
            messages = [m.copy() for m in messages]
            messages[0]["content"] += " /no_think"
        return messages

    async def _rate_limit(self) -> None:
        """速率限制：确保两次请求之间有足够间隔

        如果距离上次请求时间不足 request_delay，则等待剩余时间。
        """
        import time

        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.request_delay:
            wait_time = self.request_delay - time_since_last
            await asyncio.sleep(wait_time)

        self.last_request_time = time.time()

    async def close(self) -> None:
        """关闭 LLM 客户端并释放资源

        关闭底层的 provider 和 httpx.AsyncClient，释放网络连接。
        建议在使用完毕后或程序退出前调用此方法。

        Example:
            client = LLMClient(...)
            try:
                result = await client.generate_summary(text, title)
            finally:
                await client.close()
        """
        # 关闭 provider
        if hasattr(self, "provider") and self.provider is not None:
            await self.provider.close()

        # 关闭 client（向后兼容）
        if hasattr(self, "client") and self.client is not None:
            await self.client.close()

        logger.debug("LLMClient 已关闭")

    async def __aenter__(self) -> "LLMClient":
        """异步上下文管理器入口

        Example:
            async with LLMClient(...) as client:
                result = await client.generate_summary(text, title)
        """
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """异步上下文管理器退出，自动关闭客户端"""
        await self.close()

    def _extract_json_from_text(self, text: str) -> dict[str, Any] | None:
        """从文本中提取 JSON（栈匹配方法）

        当标准 JSON 解析失败时的备用方案。使用栈来正确匹配嵌套的
        大括号，提取第一个完整的 JSON 对象。

        Args:
            text: 包含 JSON 的文本

        Returns:
            解析后的字典，失败返回 None

        Examples:
            >>> _extract_json_from_text('前缀 {"a": 1} 后缀')
            {"a": 1}
            >>> _extract_json_from_text('前缀 {"a": {"b": 2}} 后缀')
            {"a": {"b": 2}}
        """
        # 使用栈匹配嵌套的大括号
        stack: list[int] = []  # 存储左括号的位置
        in_string = False
        escape_next = False
        quote_char = None

        for i, char in enumerate(text):
            if escape_next:
                escape_next = False
                continue

            if char == "\\":
                escape_next = True
                continue

            # 处理字符串中的引号
            if char in ('"', "'") and not in_string:
                in_string = True
                quote_char = char
                continue
            elif char == quote_char and in_string:
                in_string = False
                quote_char = None
                continue

            # 只在非字符串内容中处理大括号
            if not in_string:
                if char == "{":
                    stack.append(i)
                elif char == "}" and stack:
                    # 找到匹配的左括号（栈顶是最内层的 {）
                    start = stack.pop()
                    if not stack:
                        # 栈为空，找到完整的 JSON 对象
                        json_str = text[start : i + 1]
                        try:
                            return cast(dict[str, Any] | None, json.loads(json_str))
                        except json.JSONDecodeError:
                            # 继续尝试下一个可能的 JSON 对象
                            continue

        # 如果使用栈方法失败，回退到简单方法
        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1 or end <= start:
            return None

        json_str = text[start : end + 1]
        try:
            return cast(dict[str, Any] | None, json.loads(json_str))
        except json.JSONDecodeError:
            return None

    # ============================================================
    # 向后兼容：摘要生成方法（委托给 SummaryGenerator）
    # ============================================================

    @property
    def _summary_generator(self) -> "SummaryGenerator":
        """延迟导入 SummaryGenerator"""
        from .summary_generator import SummaryGenerator

        if not hasattr(self, "_summary_generator_instance"):
            self._summary_generator_instance = SummaryGenerator(self)
        return self._summary_generator_instance

    @property
    def _hierarchical_summarizer(self) -> "HierarchicalSummarizer":
        """延迟导入 HierarchicalSummarizer"""
        from .hierarchical_summarizer import HierarchicalSummarizer

        if not hasattr(self, "_hierarchical_summarizer_instance"):
            self._hierarchical_summarizer_instance = HierarchicalSummarizer(self)
        return self._hierarchical_summarizer_instance

    async def generate_summary(self, text: str, title: str, max_retries: int = 8) -> dict[str, Any] | None:
        """生成结构化摘要（委托给 SummaryGenerator）

        Args:
            text: 待摘要的文本内容
            title: 文本标题
            max_retries: 最大重试次数

        Returns:
            包含 one_line, key_points, detailed_summary, concepts 的字典
        """
        return await self._summary_generator.generate_summary(text, title, max_retries)

    async def generate_summary_smart(
        self, text: str, title: str, direct_limit: int = 10000, max_retries: int = 8
    ) -> dict[str, Any] | None:
        """智能摘要：根据文本长度自动选择策略

        Args:
            text: 待摘要的文本
            title: 文本标题
            direct_limit: 直接摘要的字符数上限（默认 1 万字）
            max_retries: 最大重试次数

        Returns:
            包含 one_line, key_points, detailed_summary, concepts 的字典
        """
        return await self._summary_generator.generate_summary_smart(
            text, title, direct_limit, max_retries
        )

    async def generate_map_reduce_summary(
        self, text: str, title: str, max_retries: int = 8, chunk_size: int = 4000, overlap: int = 200
    ) -> dict[str, Any] | None:
        """Map-Reduce 摘要（委托给 HierarchicalSummarizer）

        Args:
            text: 待摘要的文本
            title: 文本标题
            max_retries: 最大重试次数
            chunk_size: 分块大小（字符数）
            overlap: 重叠字符数

        Returns:
            包含 one_line, key_points, detailed_summary, concepts 的字典
        """
        return await self._hierarchical_summarizer.generate_map_reduce_summary(
            text, title, max_retries, chunk_size, overlap
        )

    async def generate_hierarchical_summary(
        self, text: str, title: str, max_retries: int = 8, chunk_size: int = 4000, overlap: int = 200
    ) -> dict[str, Any] | None:
        """分层摘要（委托给 HierarchicalSummarizer）

        Args:
            text: 待摘要的文本
            title: 文本标题
            max_retries: 最大重试次数
            chunk_size: 分块大小（字符数）
            overlap: 重叠字符数

        Returns:
            包含 one_line, key_points, detailed_summary, concepts 的字典
        """
        return await self._hierarchical_summarizer.generate_hierarchical_summary(
            text, title, max_retries, chunk_size, overlap
        )


# ============================================================
# 向后兼容：导出新类（允许旧的 import 路径继续工作）
# ============================================================
from .hierarchical_summarizer import HierarchicalSummarizer  # noqa: E402
from .summary_generator import SummaryGenerator  # noqa: E402

__all__ = ["LLMClient", "SummaryGenerator", "HierarchicalSummarizer"]
