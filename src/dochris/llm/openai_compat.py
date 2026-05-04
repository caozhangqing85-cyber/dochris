#!/usr/bin/env python3
"""OpenAI 兼容 API 提供商

支持任何 OpenAI API 兼容的服务：
- 智谱 AI (https://open.bigmodel.cn)
- DeepSeek (https://api.deepseek.com)
- OpenAI (https://api.openai.com)
- 其他兼容服务
"""

from __future__ import annotations

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

    def _get_client(self) -> Any:
        """获取或创建 AsyncOpenAI 客户端

        Returns:
            AsyncOpenAI 实例

        Raises:
            ImportError: openai 包未安装时抛出
        """
        if self._client is None:
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
                    # 原先 max_connections=1 导致所有请求串行（性能评审）
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
        client = self._get_client()
        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature or self.temperature,
            **kwargs,
        )
        return response.choices[0].message.content or ""

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
