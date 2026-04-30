#!/usr/bin/env python3
"""
向量存储切换示例

演示如何使用不同的向量存储后端。

使用方法:
    python examples/05_vector_store.py

输出:
    - 显示所有可用的向量存储及其描述
"""
from __future__ import annotations


def main() -> None:
    """执行向量存储示例"""
    from dochris.vector import STORES, get_store

    print("=" * 60)
    print("可用的向量存储")
    print("=" * 60)

    for name, cls in STORES.items():
        print(f"\n{name}:")
        print(f"  类: {cls.__name__}")
        # 获取类的文档字符串
        doc = cls.__doc__ or "无描述"
        print(f"  描述: {doc.strip()}")

    print("\n" + "=" * 60)
    print("获取向量存储类")
    print("=" * 60)

    # 获取 ChromaDB 存储
    chroma_store = get_store("chromadb")
    print(f"\nchromadb 向量存储类: {chroma_store.__name__}")

    # 显示初始化参数
    import inspect

    sig = inspect.signature(chroma_store.__init__)
    print(f"初始化参数:")
    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue
        default = param.default if param.default != inspect.Parameter.empty else "必需"
        print(f"  - {param_name}: {default}")

    # 检查 FAISS 是否可用
    if "faiss" in STORES:
        faiss_store = get_store("faiss")
        print(f"\nfaiss 向量存储类: {faiss_store.__name__}")
        print("  (FAISS 是可选依赖，需要安装: pip install faiss-cpu)")
    else:
        print("\nfaiss 不可用 (需要安装: pip install faiss-cpu)")

    print("\n提示:")
    print("  1. 在 .env 文件中设置 VECTOR_STORE 环境变量")
    print("  2. 或在代码中使用 get_store('store_name') 获取存储类")


if __name__ == "__main__":
    main()
