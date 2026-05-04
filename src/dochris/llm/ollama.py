#!/usr/bin/env python3
"""Ollama 本地模型提供商

使用 Ollama REST API 进行本地推理，无需 API Key。
"""

from __future__ import annotations

import logging
from typing import Any

try:
    import aiohttp
except ImportError:
    logging.warning("aiohttp not installed. Ollama provider requires: pip install aiohttp")
    aiohttp = None  # type: ignore

from .base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Ollama 本地模型提供商

    使用 Ollama REST API (http://localhost:11434) 进行本地推理。
    支持任何 Ollama 支持的模型（如 qwen:14b, llama2:13b 等）。

    Attributes:
        name: 提供商名称
        base_url: Ollama API 基础 URL
    """

    name = "ollama"

    def __init__(self, **kwargs: Any) -> None:
        """初始化 Ollama 提供商

        Args:
            **kwargs: 传递给 BaseLLMProvider 的参数
                      api_base 默认为 http://localhost:11434
        """
        # Ollama 默认不需要 api_key
        kwargs.setdefault("api_key", "")
        super().__init__(**kwargs)

        # 确定 base_url
        api_base = kwargs.get("api_base")
        self.base_url = api_base if api_base else "http://localhost:11434"

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
            **kwargs: 其他参数（忽略，Ollama API 有固定格式）

        Returns:
            生成的文本
        """
        if aiohttp is None:
            raise ImportError("aiohttp package not installed. Run: pip install aiohttp")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        return await self.generate_with_messages(
            messages, max_tokens=max_tokens, temperature=temperature
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
            **kwargs: 其他参数（忽略）

        Returns:
            生成的文本
        """
        if aiohttp is None:
            raise ImportError("aiohttp package not installed. Run: pip install aiohttp")

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens or self.max_tokens,
                "temperature": temperature or self.temperature,
            },
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()

        return str(data.get("message", {}).get("content", ""))


__all__ = ["OllamaProvider"]
