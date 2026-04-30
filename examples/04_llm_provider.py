#!/usr/bin/env python3
"""
LLM 提供商切换示例

演示如何使用不同的 LLM 提供商。

使用方法:
    python examples/04_llm_provider.py

输出:
    - 显示所有可用的 LLM 提供商及其描述
"""
from __future__ import annotations


def main() -> None:
    """执行 LLM 提供商示例"""
    from dochris.llm import PROVIDERS, get_provider

    print("=" * 60)
    print("可用的 LLM 提供商")
    print("=" * 60)

    for name, cls in PROVIDERS.items():
        print(f"\n{name}:")
        print(f"  类: {cls.__name__}")
        # 获取类的文档字符串
        doc = cls.__doc__ or "无描述"
        print(f"  描述: {doc.strip()}")

    print("\n" + "=" * 60)
    print("获取提供商类")
    print("=" * 60)

    # 获取 OpenAI 兼容提供商
    openai_provider = get_provider("openai_compat")
    print(f"\nopenai_compat 提供商类: {openai_provider.__name__}")

    # 显示初始化参数（从 __init__ 签名）
    import inspect

    sig = inspect.signature(openai_provider.__init__)
    print(f"初始化参数:")
    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue
        default = param.default if param.default != inspect.Parameter.empty else "必需"
        print(f"  - {param_name}: {default}")

    print("\n提示:")
    print("  1. 在 .env 文件中设置 LLM_PROVIDER 环境变量")
    print("  2. 或在代码中使用 get_provider('provider_name') 获取提供商类")


if __name__ == "__main__":
    main()
