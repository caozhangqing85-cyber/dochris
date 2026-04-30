"""查询增强插件示例

演示 pre_query 和 post_query hook 的使用。

功能：
1. 查询前：展开常见缩写
2. 查询后：过滤低分结果

使用方法：
1. 将此文件复制到 ~/.knowledge-base/plugins/
2. 或在 .env 中设置: PLUGIN_DIRS=/path/to/examples/plugins
"""

from __future__ import annotations

import logging
from typing import Any

# 导入 dochris 插件装饰器
from dochris.plugin import hookimpl

logger = logging.getLogger(__name__)


# 常见缩写映射
ABBREVIATIONS: dict[str, str] = {
    "kb": "knowledge base",
    "ai": "artificial intelligence",
    "ml": "machine learning",
    "dl": "deep learning",
    "nlp": "natural language processing",
    "llm": "large language model",
}


@hookimpl
def pre_query(query: str) -> str:
    """查询前处理：展开常见缩写

    Args:
        query: 原始查询

    Returns:
        处理后的查询
    """
    processed = query
    for abbr, full in ABBREVIATIONS.items():
        # 匹配单词边界
        import re

        pattern = r"\b" + abbr + r"\b"
        processed = re.sub(pattern, full, processed, flags=re.IGNORECASE)

    if processed != query:
        logger.info(f"查询扩展: {query} → {processed}")

    return processed


@hookimpl
def post_query(query: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """查询后处理：过滤低分结果

    Args:
        query: 查询文本
        results: 查询结果列表

    Returns:
        过滤后的结果列表
    """
    # 提取所有结果
    all_results: list[dict[str, Any]] = []

    # results 可能包含嵌套结构
    for result in results:
        if isinstance(result, dict):
            # 处理 search_all 返回的格式
            for key in ["concepts", "summaries", "vector_results"]:
                if key in result and isinstance(result[key], list):
                    all_results.extend(result[key])
        elif isinstance(result, list):
            all_results.extend(result)

    # 过滤低分结果（score < 0.1）
    min_score = 0.1
    filtered = [r for r in all_results if r.get("score", 1) >= min_score]

    if len(filtered) < len(all_results):
        logger.info(f"结果过滤: {len(all_results)} → {len(filtered)} (移除 {len(all_results) - len(filtered)} 个低分结果)")

    return filtered
