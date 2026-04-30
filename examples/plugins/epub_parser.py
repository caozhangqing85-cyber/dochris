"""EPUB 文件解析插件示例

使用方法：
1. pip install ebooklib
2. 将此文件复制到 ~/.knowledge-base/plugins/
3. 或在 .env 中设置: PLUGIN_DIRS=/path/to/examples/plugins

示例：
    export PLUGIN_DIRS=/home/user/.knowledge-base/plugins:/path/to/examples/plugins
"""

from __future__ import annotations

import logging

# 导入 dochris 插件装饰器
from dochris.plugin import hookimpl

logger = logging.getLogger(__name__)


@hookimpl
def ingest_parser(file_path: str) -> str | None:
    """解析 EPUB 文件

    Args:
        file_path: EPUB 文件路径

    Returns:
        提取的文本内容，None 表示不处理此文件
    """
    if not file_path.lower().endswith(".epub"):
        return None

    try:
        from ebooklib import epub

        book = epub.read_epub(file_path)
        texts: list[str] = []

        for item in book.get_items_of_type(9):  # ITEM_DOCUMENT = 9
            content = item.get_content().decode("utf-8", errors="replace")
            # 简单的 HTML 标签清理
            import re

            content = re.sub(r"<[^>]+>", "", content)
            content = " ".join(content.split())
            if len(content) > 50:  # 过滤过短的片段
                texts.append(content)

        if texts:
            logger.info(f"EPUB 解析成功: {file_path} ({len(texts)} 段落)")
            return "\n\n".join(texts)

        logger.warning(f"EPUB 内容为空: {file_path}")
        return None

    except ImportError:
        logger.warning("ebooklib 未安装，无法解析 EPUB 文件")
        logger.info("安装命令: pip install ebooklib")
        return None
    except Exception as e:
        logger.error(f"EPUB 解析失败 {file_path}: {e}")
        return None
