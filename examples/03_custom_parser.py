#!/usr/bin/env python3
"""
自定义解析器示例

演示如何通过插件系统注册自定义文件解析器。

使用方法:
    1. 在你的插件目录中创建此文件
    2. 设置环境变量: export PLUGIN_DIRS=/path/to/your/plugins
    3. 运行: python examples/03_custom_parser.py

输出:
    - 显示自定义解析器是否成功注册
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


# 定义自定义解析器
def custom_csv_parser(file_path: str) -> str | None:
    """自定义 CSV 解析器

    将 CSV 文件转换为可读的文本格式。

    Args:
        file_path: CSV 文件路径

    Returns:
        转换后的文本，如果不是 CSV 文件则返回 None
    """
    if not file_path.endswith(".csv"):
        return None

    try:
        import csv

        rows = []
        with open(file_path, encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                rows.append(" | ".join(row))

        return "\n".join(rows)
    except Exception as e:
        print(f"CSV 解析失败: {e}")
        return None


def main() -> None:
    """执行自定义解析器示例"""
    from dochris.plugin import PluginManager, hookimpl
    from dochris.plugin.hookspec import hookspec

    # 创建插件管理器
    pm = PluginManager()

    print("=" * 60)
    print("自定义解析器示例")
    print("=" * 60)

    # 方法 1: 使用 @hookimpl 装饰器
    print("\n方法 1: 使用 @hookimpl 装饰器")

    @hookimpl
    def ingest_parser(file_path: str) -> str | None:
        """自定义 TOML 解析器"""
        if not file_path.endswith(".toml"):
            return None
        try:
            from pathlib import Path

            return Path(file_path).read_text(encoding="utf-8")
        except Exception:
            return None

    # 注册 hook
    pm.register("custom_plugin", "ingest_parser", ingest_parser)
    print(f"✅ 已注册 ingest_parser hook")

    # 方法 2: 创建一个测试 CSV 文件并解析
    print("\n方法 2: 测试自定义解析器")
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试 CSV 文件
        csv_path = Path(tmpdir) / "test.csv"
        csv_path.write_text("Name,Age,City\nAlice,30,Beijing\nBob,25,Shanghai")

        # 使用自定义解析器
        result = custom_csv_parser(str(csv_path))
        if result:
            print(f"✅ CSV 解析成功:")
            print(result)
        else:
            print("❌ CSV 解析失败")

    # 列出所有注册的 hook
    print("\n当前注册的 hooks:")
    plugins = pm.list_plugins()
    for p in plugins:
        hooks = p.get("hooks", [])
        if hooks:
            print(f"  - {p['name']}: {', '.join(hooks)}")


if __name__ == "__main__":
    main()
