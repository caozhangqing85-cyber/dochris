#!/usr/bin/env python3
"""LLM 提供商抽象层

提供统一的 LLM 提供商接口，支持多种 LLM 服务：
- OpenAI 兼容 API（智谱、DeepSeek、OpenAI 等）
- Ollama 本地模型

用法:
    from dochris.llm import get_provider, PROVIDERS

    # 获取提供商类
    provider_class = get_provider("openai_compat")
    provider = provider_class(api_key="xxx", api_base="...", model="glm-5.1")

    # 查看可用提供商
    print(list(PROVIDERS.keys()))  # ['openai_compat', 'ollama']
"""

from __future__ import annotations

from dochris.llm.base import BaseLLMProvider
from dochris.llm.ollama import OllamaProvider
from dochris.llm.openai_compat import OpenAICompatProvider

__all__ = ["BaseLLMProvider", "OpenAICompatProvider", "OllamaProvider", "PROVIDERS", "get_provider"]

# 提供商注册表
PROVIDERS: dict[str, type[BaseLLMProvider]] = {
    "openai_compat": OpenAICompatProvider,
    "ollama": OllamaProvider,
}


def get_provider(name: str) -> type[BaseLLMProvider]:
    """获取提供商类

    Args:
        name: 提供商名称（openai_compat 或 ollama）

    Returns:
        提供商类

    Raises:
        ValueError: 提供商不存在时

    Examples:
        >>> provider_cls = get_provider("openai_compat")
        >>> provider = provider_cls(api_key="xxx", model="glm-5.1")
    """
    if name not in PROVIDERS:
        available = ", ".join(PROVIDERS.keys())
        raise ValueError(f"Unknown LLM provider: {name!r}. Available: {available}")
    return PROVIDERS[name]
