#!/usr/bin/env python3
"""LLM 提供商抽象基类"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseLLMProvider(ABC):
    """LLM 提供商基类

    所有 LLM 提供商必须实现此接口，确保统一的调用方式。

    Attributes:
        name: 提供商名称
        api_key: API 密钥
        api_base: API 基础 URL
        model: 模型名称
        max_tokens: 最大生成 token 数
        temperature: 采样温度
        timeout: 请求超时时间（秒）
    """

    name: str = "base"

    def __init__(
        self,
        api_key: str = "",
        api_base: str | None = None,
        model: str = "",
        max_tokens: int = 4000,
        temperature: float = 0.7,
        timeout: int = 120,
        **kwargs: Any,
    ) -> None:
        """初始化 LLM 提供商

        Args:
            api_key: API 密钥（某些提供商如 Ollama 不需要）
            api_base: API 基础 URL
            model: 模型名称
            max_tokens: 最大生成 token 数
            temperature: 采样温度（0.0-1.0）
            timeout: 请求超时时间（秒）
            **kwargs: 其他提供商特定参数
        """
        self.api_key = api_key
        self.api_base = api_base
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout

    @abstractmethod
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
            max_tokens: 最大生成 token 数（覆盖默认值）
            temperature: 采样温度（覆盖默认值）
            **kwargs: 其他提供商特定参数

        Returns:
            生成的文本
        """
        ...

    @abstractmethod
    async def generate_with_messages(
        self,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> str:
        """基于消息列表生成文本

        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]
            max_tokens: 最大生成 token 数（覆盖默认值）
            temperature: 采样温度（覆盖默认值）
            **kwargs: 其他提供商特定参数

        Returns:
            生成的文本
        """
        ...

    async def close(self) -> None:  # noqa: B027
        """清理资源

        默认实现为空，子类可根据需要重写。
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model!r})"


__all__ = ["BaseLLMProvider"]
