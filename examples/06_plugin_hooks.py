#!/usr/bin/env python3
"""
完整插件 Hook 示例

演示所有 6 个插件扩展点的使用方法。

使用方法:
    1. 将此文件复制到你的插件目录
    2. 设置环境变量: export PLUGIN_DIRS=/path/to/your/plugins
    3. 运行: python examples/06_plugin_hooks.py

输出:
    - 显示所有 hook 的注册和测试结果
"""
from __future__ import annotations

from typing import Any


def main() -> None:
    """执行完整插件 Hook 示例"""
    from dochris.plugin import PluginManager, hookimpl

    print("=" * 60)
    print("Dochris 插件系统 - 完整 Hook 示例")
    print("=" * 60)

    # 创建插件管理器
    pm = PluginManager()

    # ============================================================
    # Hook 1: ingest_parser - 自定义文件解析器
    # ============================================================
    @hookimpl
    def ingest_parser(file_path: str) -> str | None:
        """自定义日志文件解析器"""
        if not file_path.endswith(".log"):
            return None

        from pathlib import Path

        try:
            content = Path(file_path).read_text(encoding="utf-8")
            # 只提取 ERROR 和 WARNING 行
            lines = [l for l in content.split("\n") if "ERROR" in l or "WARNING" in l]
            return "\n".join(lines)
        except Exception:
            return None

    pm.register("demo_hooks", "ingest_parser", ingest_parser)
    print("✅ Hook 1: ingest_parser - 自定义 .log 文件解析器")

    # ============================================================
    # Hook 2: pre_compile - 编译前处理
    # ============================================================
    @hookimpl
    def pre_compile(text: str, metadata: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """编译前：去除多余空行和特殊字符"""
        # 去除多余空行
        cleaned = "\n".join(line for line in text.split("\n") if line.strip())
        # 去除 NULL 字符
        cleaned = cleaned.replace("\x00", "")
        # 添加处理标记
        metadata["pre_processed"] = True
        return cleaned, metadata

    pm.register("demo_hooks", "pre_compile", pre_compile)
    print("✅ Hook 2: pre_compile - 清理空行和特殊字符")

    # ============================================================
    # Hook 3: post_compile - 编译后处理
    # ============================================================
    @hookimpl
    def post_compile(src_id: str, result: dict[str, Any]) -> None:
        """编译后：打印日志"""
        status = result.get("status", "unknown")
        if status == "compiled":
            quality = result.get("result", {}).get("quality_score", 0)
            print(f"📢 [Hook] 编译完成: {src_id} [质量: {quality}/100]")
        else:
            print(f"⚠️  [Hook] 编译异常: {src_id} - {status}")

    pm.register("demo_hooks", "post_compile", post_compile)
    print("✅ Hook 3: post_compile - 编译完成通知")

    # ============================================================
    # Hook 4: quality_score - 自定义质量评分
    # ============================================================
    @hookimpl
    def quality_score(text: str, metadata: dict[str, Any] | None = None) -> float | None:
        """自定义评分：短文本降权"""
        if len(text) < 100:
            # 短文本最高 30 分
            return 30.0
        # 长文本使用默认评分
        return None

    pm.register("demo_hooks", "quality_score", quality_score)
    print("✅ Hook 4: quality_score - 短文本降权评分")

    # ============================================================
    # Hook 5: pre_query - 查询前处理
    # ============================================================
    @hookimpl
    def pre_query(query: str) -> str:
        """查询前：去除多余空格，展开缩写"""
        # 去除多余空格
        cleaned = " ".join(query.split())
        # 展开常见缩写
        expansions = {
            "kb": "knowledge base",
            "llm": "large language model",
            "ai": "artificial intelligence",
        }
        for abbr, full in expansions.items():
            cleaned = cleaned.lower().replace(abbr, full)
        return cleaned

    pm.register("demo_hooks", "pre_query", pre_query)
    print("✅ Hook 5: pre_query - 清理和扩展查询")

    # ============================================================
    # Hook 6: post_query - 查询后处理
    # ============================================================
    @hookimpl
    def post_query(query: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """查询后：限制结果数量，按分数排序"""
        # 限制最多返回 5 个结果
        limited = results[:5]
        # 按分数降序排序（如果有 score 字段）
        if limited and "score" in limited[0]:
            limited = sorted(limited, key=lambda x: x.get("score", 0), reverse=True)
        return limited

    pm.register("demo_hooks", "post_query", post_query)
    print("✅ Hook 6: post_query - 限制和排序结果")

    # ============================================================
    # 测试 Hooks
    # ============================================================
    print("\n" + "=" * 60)
    print("测试 Hooks")
    print("=" * 60)

    # 测试 pre_compile
    print("\n测试 pre_compile:")
    test_text = "Hello\n\n\nWorld\x00"
    test_metadata = {}
    result_text, result_meta = pm.call_hook("pre_compile", test_text, test_metadata)
    print(f"  原始: {repr(test_text)}")
    print(f"  处理后: {repr(result_text)}")
    print(f"  元数据: {result_meta}")

    # 测试 quality_score
    print("\n测试 quality_score:")
    short_text = "Short text"
    score = pm.call_hook("quality_score", short_text)
    print(f"  短文本: {repr(short_text)}")
    print(f"  评分: {score}")

    long_text = "This is a much longer text that exceeds one hundred characters to ensure it passes the minimum length threshold for custom quality scoring in this example plugin hook demonstration."
    score = pm.call_hook("quality_score", long_text)
    print(f"  长文本: {len(long_text)} 字符")
    print(f"  评分: {score} (None = 使用默认评分)")

    # 测试 pre_query
    print("\n测试 pre_query:")
    test_query = "  What  is  kb?  "
    result_query = pm.call_hook("pre_query", test_query)
    print(f"  原始: {repr(test_query)}")
    print(f"  处理后: {repr(result_query)}")

    # 测试 post_query
    print("\n测试 post_query:")
    test_results = [
        {"id": 1, "score": 0.7},
        {"id": 2, "score": 0.9},
        {"id": 3, "score": 0.5},
        {"id": 4, "score": 0.8},
        {"id": 5, "score": 0.6},
        {"id": 6, "score": 0.4},
    ]
    result_list = pm.call_hook("post_query", "test", test_results)
    print(f"  原始结果数: {len(test_results)}")
    print(f"  处理后结果数: {len(result_list)}")
    print(f"  结果顺序: {[r['id'] for r in result_list]}")

    # ============================================================
    # 列出所有插件
    # ============================================================
    print("\n" + "=" * 60)
    print("已注册的插件")
    print("=" * 60)
    plugins = pm.list_plugins()
    for p in plugins:
        hooks = p.get("hooks", [])
        print(f"\n插件: {p['name']}")
        if hooks:
            print(f"  Hooks: {', '.join(hooks)}")


if __name__ == "__main__":
    main()
