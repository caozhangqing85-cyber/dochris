#!/usr/bin/env python3
"""
质量评分示例

演示如何对文本进行质量评分。

使用方法:
    python examples/02_quality_scoring.py

输出:
    - 显示示例文本的质量评分（0-100 分）
"""
from __future__ import annotations


def main() -> None:
    """执行质量评分示例"""
    # 导入质量评分函数
    from dochris.core.quality_scorer import score_summary_quality_v4

    # 示例 1: 高质量内容
    print("=" * 60)
    print("示例 1: 高质量内容")
    print("=" * 60)

    sample_good = {
        "detailed_summary": """Python 装饰器是一种强大的语法特性，允许在不修改原始函数代码的情况下，
为函数添加额外的功能。装饰器本质上是一个接受函数作为参数并返回新函数的高阶函数。

学习装饰器的关键点：
1. 理解闭包机制：装饰器依赖于闭包，内部函数可以访问外部函数的变量
2. 函数即对象：在 Python 中，函数是一等公民，可以作为参数传递
3. @语法糖：@decorator 只是 foo = decorator(foo) 的简写形式

实际应用场景包括：
- 日志记录：自动记录函数调用信息
- 性能测试：计算函数执行时间
- 权限验证：检查用户是否有权限执行操作
- 缓存机制：缓存函数结果避免重复计算

掌握装饰器可以显著提升代码的可维护性和复用性，是 Python 高级编程的重要技能。
        """,
        "key_points": [
            "装饰器是 Python 的语法糖，本质是高阶函数",
            "理解闭包是掌握装饰器的关键",
            "装饰器可以用于日志、性能测试、权限验证等场景",
            "使用装饰器可以提高代码的可维护性和复用性",
        ],
        "concepts": ["装饰器", "闭包", "高阶函数", "一等公民", "语法糖"],
        "one_line": "Python 装饰器详解：从原理到实践",
    }

    score = score_summary_quality_v4(sample_good)
    print(f"标题: {sample_good['one_line']}")
    print(f"质量评分: {score}/100")
    print(f"评级: {'✅ 优秀' if score >= 85 else '⚠️ 需改进'}")

    # 示例 2: 低质量内容
    print("\n" + "=" * 60)
    print("示例 2: 低质量内容")
    print("=" * 60)

    sample_poor = {
        "detailed_summary": "这是一个摘要",
        "key_points": [],
        "concepts": [],
        "one_line": "标题",
    }

    score = score_summary_quality_v4(sample_poor)
    print(f"标题: {sample_poor['one_line']}")
    print(f"质量评分: {score}/100")
    print(f"评级: {'✅ 优秀' if score >= 85 else '⚠️ 需改进'}")

    # 示例 3: 中等质量内容
    print("\n" + "=" * 60)
    print("示例 3: 中等质量内容")
    print("=" * 60)

    sample_medium = {
        "detailed_summary": "机器学习是人工智能的一个分支。它通过数据训练模型来预测结果。"
        "常见的算法包括线性回归、决策树和神经网络。",
        "key_points": ["机器学习是 AI 的分支", "需要数据训练", "有多种算法"],
        "concepts": ["机器学习", "人工智能"],
        "one_line": "机器学习简介",
    }

    score = score_summary_quality_v4(sample_medium)
    print(f"标题: {sample_medium['one_line']}")
    print(f"质量评分: {score}/100")
    print(f"评级: {'✅ 优秀' if score >= 85 else '⚠️ 需改进'}")


if __name__ == "__main__":
    main()
