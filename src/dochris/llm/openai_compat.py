#!/usr/bin/env python3
"""OpenAI 兼容 API 提供商

支持任何 OpenAI API 兼容的服务：
- 智谱 AI (https://open.bigmodel.cn)
- DeepSeek (https://api.deepseek.com)
- OpenAI (https://api.openai.com)
- 其他兼容服务
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from .base import BaseLLMProvider


class OpenAICompatProvider(BaseLLMProvider):
    """OpenAI 兼容 API 提供商

    使用 OpenAI Python SDK 的 AsyncOpenAI 客户端连接任何兼容
    OpenAI API 的服务。

    Attributes:
        name: 提供商名称
    """

    name = "openai_compat"

    def __init__(self, **kwargs: Any) -> None:
        """初始化 OpenAI 兼容提供商

        Args:
            **kwargs: 传递给 BaseLLMProvider 的参数
        """
        super().__init__(**kwargs)
        self._client: Any = None
        # 客户端创建锁（_get_client 是同步方法，用 threading.Lock 双重检查）
        import threading

        self._client_lock = threading.Lock()

    def _get_client(self) -> Any:
        """获取或创建 AsyncOpenAI 客户端

        Returns:
            AsyncOpenAI 实例

        Raises:
            ImportError: openai 包未安装时抛出
        """
        if self._client is None:
            with self._client_lock:
                if self._client is not None:
                    return self._client
                try:
                    from openai import AsyncOpenAI
                except ImportError as e:
                    raise ImportError("openai package not installed. Run: pip install openai") from e

                import httpx

                self._client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.api_base,
                    max_retries=0,
                    timeout=self.timeout,
                    http_client=httpx.AsyncClient(
                        # 连接池扩大：max_concurrency=3 配置需要匹配的连接池上限
                        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
                        timeout=self.timeout,
                    ),
                )
        return self._client

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> str:
        """生成文本

        Args:
            prompt: 用户提示
            system_prompt: 系统提示（可选）
            max_tokens: 最大生成 token 数
            temperature: 采样温度
            **kwargs: 其他参数（传递给 API）

        Returns:
            生成的文本
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        return await self.generate_with_messages(
            messages, max_tokens=max_tokens, temperature=temperature, **kwargs
        )

    async def generate_with_messages(
        self,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> str:
        """基于消息列表生成文本

        Args:
            messages: 消息列表
            max_tokens: 最大生成 token 数
            temperature: 采样温度
            **kwargs: 其他参数（传递给 API）

        Returns:
            生成的文本
        """
        import time

        start = time.time()
        error_type: str | None = None

        try:
            client = self._get_client()
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
                temperature=temperature if temperature is not None else self.temperature,
                **kwargs,
            )

            # 记录 LLM usage（可观测性）
            latency_ms = (time.time() - start) * 1000
            self._record_usage(response, latency_ms, "generate_with_messages")

            return response.choices[0].message.content or ""
        except Exception as e:
            error_type = type(e).__name__
            latency_ms = (time.time() - start) * 1000
            self._record_usage_error(latency_ms, "generate_with_messages", error_type)
            raise

    def _record_usage(self, response: Any, latency_ms: float, operation: str) -> None:
        """记录 LLM 调用到可观测性系统。"""
        try:
            from dochris.observability import get_observability

            obs = get_observability()
            if not obs.enabled:
                return

            usage = getattr(response, "usage", None)
            prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(usage, "completion_tokens", 0) or 0
            total_tokens = getattr(usage, "total_tokens", 0) or 0

            from dochris.observability.metrics import LLMUsage

            llm_usage = LLMUsage(
                provider="openai_compat",
                model=self.model,
                operation=operation,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
            )
            obs.record_llm_usage(llm_usage)
        except Exception:
            # 可观测性记录失败不应影响正常调用
            pass

    def _record_usage_error(
        self, latency_ms: float, operation: str, error_type: str
    ) -> None:
        """记录 LLM 调用错误。"""
        try:
            from dochris.observability import get_observability
            from dochris.observability.metrics import LLMUsage

            obs = get_observability()
            if not obs.enabled:
                return

            llm_usage = LLMUsage(
                provider="openai_compat",
                model=self.model,
                operation=operation,
                latency_ms=latency_ms,
                error_type=error_type,
            )
            obs.record_llm_usage(llm_usage)
        except Exception:
            pass

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """流式生成文本，逐 chunk yield。

        使用 AsyncOpenAI 的 stream=True 模式。

        Yields:
            str: 每个 chunk 的文本内容
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        client = self._get_client()
        stream = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
            temperature=temperature if temperature is not None else self.temperature,
            stream=True,
            **kwargs,
        )
        try:
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content
        finally:
            # 显式关闭 stream 释放底层 HTTP 连接（异常或提前退出时尤为重要）
            close = getattr(stream, "close", None)
            if close is not None:
                try:
                    result = close()
                    if hasattr(result, "__await__"):
                        await result
                except Exception:
                    pass

    async def close(self) -> None:
        """关闭客户端连接"""
        if self._client is not None:
            await self._client.close()
            self._client = None

    @property
    def client(self) -> Any:
        """暴露底层的 AsyncOpenAI 客户端

        这是为了向后兼容性，允许直接访问 client.chat.completions.create()。
        """
        return self._get_client()


__all__ = ["OpenAICompatProvider"]
