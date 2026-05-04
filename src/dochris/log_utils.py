#!/usr/bin/env python3
"""
统一的日志工具模块

提供：
1. get_logger() - 获取标准 logger 实例
2. append_log_to_file() - 追加日志到 JSON 文件
3. append_log_to_markdown() - 追加日志到 Markdown 文件
4. setup_logging() - 配置日志系统
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# 模块级别 logger
logger = logging.getLogger(__name__)

# 日志格式
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str) -> logging.Logger:
    """获取标准 logger 实例

    Args:
        name: logger 名称，通常使用 __name__

    Returns:
        配置好的 Logger 实例

    Example:
        from dochris.log_utils import get_logger
        logger = get_logger(__name__)
        logger.info("消息")
    """
    return logging.getLogger(name)


def setup_logging(
    level: int = logging.INFO,
    log_format: str = DEFAULT_LOG_FORMAT,
    date_format: str = DEFAULT_DATE_FORMAT,
    log_file: Path | None = None,
    also_console: bool = True,
) -> None:
    """配置日志系统

    Args:
        level: 日志级别（默认 INFO）
        log_format: 日志格式
        date_format: 日期格式
        log_file: 日志文件路径（可选）
        also_console: 是否同时输出到控制台（默认 True）

    Example:
        from dochris.log_utils import setup_logging
        setup_logging(log_file=Path("app.log"), level=logging.DEBUG)
    """
    handlers: list[logging.Handler] = []

    # 文件处理器
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    # 控制台处理器
    if also_console:
        handlers.append(logging.StreamHandler(sys.stdout))

    logging.basicConfig(
        level=level,
        format=log_format,
        datefmt=date_format,
        handlers=handlers,
    )


def get_default_workspace() -> Path:
    """获取默认工作区路径

    Returns:
        默认工作区路径
    """
    return Path.home() / ".openclaw/knowledge-base"


def append_log_to_file(workspace: Path | None, message: str, log_type: str = "system") -> None:
    """追加日志条目到系统日志文件（JSON 格式）

    Args:
        workspace: 工作区路径，None 时使用默认路径
        message: 日志消息
        log_type: 日志类型（system, compile, ingest 等）
    """
    # 使用传入的 workspace 参数，fallback 到默认路径
    log_dir = get_default_workspace() / "logs" if workspace is None else workspace / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_entry = {"timestamp": datetime.now().isoformat(), "type": log_type, "message": message}

    log_file = log_dir / f"{log_type}_{datetime.now().strftime('%Y%m%d')}.json"

    logs = []
    if log_file.exists():
        with open(log_file, encoding="utf-8") as f:
            try:
                logs = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load log file {log_file}: {e}")
                logs = []

    logs.append(log_entry)

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


def append_log_to_markdown(workspace_path: Path | None, operation: str, detail: str) -> None:
    """追加日志到 log.md（Markdown 格式）

    Args:
        workspace_path: 工作区路径，None 时使用默认路径
        operation: 操作类型（如 ingest, compile, promote）
        detail: 操作详情
    """
    workspace = get_default_workspace() if workspace_path is None else Path(workspace_path)
    log_path = workspace / "log.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## [{timestamp}] {operation} | {detail}\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)


def append_log_multi_to_markdown(
    workspace_path: Path | None, operation: str, details: list[str]
) -> None:
    """批量追加日志到 log.md（同一操作，多条 detail）

    Args:
        workspace_path: 工作区路径，None 时使用默认路径
        operation: 操作类型
        details: 操作详情列表
    """
    workspace = get_default_workspace() if workspace_path is None else Path(workspace_path)
    log_path = workspace / "log.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(log_path, "a", encoding="utf-8") as f:
        for detail in details:
            f.write(f"\n## [{timestamp}] {operation} | {detail}\n")
