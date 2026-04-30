#!/usr/bin/env python3
"""
append-only 日志系统
所有操作追加写入 log.md，格式：## [YYYY-MM-DD HH:MM] <operation> | <detail>

使用 log_utils 模块实现，避免重复代码。
"""

from pathlib import Path

from dochris.log_utils import (
    append_log_multi_to_markdown,
    append_log_to_markdown,
)
from dochris.settings import get_settings


def get_default_workspace() -> Path:
    """获取默认工作区路径（使用 settings 模块）"""
    return get_settings().workspace


def append_log(workspace_path: Path | str, operation: str, detail: str) -> None:
    """追加日志到 log.md

    Args:
        workspace_path: 工作区路径（Path 或 str）
        operation: 操作类型（如 ingest, compile, promote）
        detail: 操作详情
    """
    append_log_to_markdown(Path(workspace_path), operation, detail)


def append_log_multi(workspace_path: Path | str, operation: str, details: list[str]) -> None:
    """批量追加日志（同一操作，多条 detail）

    Args:
        workspace_path: 工作区路径（Path 或 str）
        operation: 操作类型
        details: 操作详情列表
    """
    append_log_multi_to_markdown(Path(workspace_path), operation, details)
