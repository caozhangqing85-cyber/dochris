#!/usr/bin/env python3
"""
文件分类函数
根据文件扩展名获取文件分类
"""

from dochris.settings.constants import FILE_TYPE_MAP, SKIP_EXTENSIONS


def get_file_category(ext: str) -> str | None:
    """根据文件扩展名获取分类

    Args:
        ext: 文件扩展名（含点号，如 '.pdf'）

    Returns:
        分类名称，如果不处理则返回 None
    """
    ext = ext.lower()
    if ext in SKIP_EXTENSIONS:
        return None
    return FILE_TYPE_MAP.get(ext, "other")
