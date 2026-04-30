#!/usr/bin/env python3
"""
环境变量读取辅助函数
提供从环境变量读取配置的辅助方法
"""

import os
from pathlib import Path


def get_env_path(env_name: str, default: Path | None = None) -> Path | None:
    """从环境变量读取路径

    Args:
        env_name: 环境变量名称
        default: 默认路径

    Returns:
        路径对象，如果环境变量未设置且无默认值则返回 None
    """
    value = os.environ.get(env_name)
    if value:
        return Path(value).expanduser()
    return default


def get_env_str(env_name: str, default: str = "") -> str:
    """从环境变量读取字符串

    Args:
        env_name: 环境变量名称
        default: 默认值

    Returns:
        字符串值
    """
    return os.environ.get(env_name, default)


def get_env_int(env_name: str, default: int = 0) -> int:
    """从环境变量读取整数

    Args:
        env_name: 环境变量名称
        default: 默认值

    Returns:
        整数值
    """
    try:
        return int(os.environ.get(env_name, str(default)))
    except ValueError:
        return default


def get_env_bool(env_name: str, default: bool = False) -> bool:
    """从环境变量读取布尔值

    Args:
        env_name: 环境变量名称
        default: 默认值

    Returns:
        布尔值
    """
    value = os.environ.get(env_name, "").lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    return default


def get_env_list(env_name: str, separator: str = ",", default: list[str] | None = None) -> list[str]:
    """从环境变量读取列表

    Args:
        env_name: 环境变量名称
        separator: 分隔符
        default: 默认值

    Returns:
        字符串列表
    """
    value = os.environ.get(env_name)
    if value:
        return [item.strip() for item in value.split(separator) if item.strip()]
    return default if default is not None else []
