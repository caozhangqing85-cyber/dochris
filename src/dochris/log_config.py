#!/usr/bin/env python3
"""日志配置模块

提供统一的日志配置，支持文本和 JSON 两种输出格式。

用法:
    from dochris.log_config import setup_logging

    # 文本格式（默认）
    setup_logging(level="INFO")

    # JSON 格式（便于 ELK/Datadog 集成）
    setup_logging(level="INFO", log_format="json")
"""

from __future__ import annotations

import json
import logging
import sys


class JSONFormatter(logging.Formatter):
    """JSON 格式日志输出，便于 ELK/Datadog 集成

    输出格式:
        {
            "timestamp": "2024-01-01 12:00:00",
            "level": "INFO",
            "module": "cli_main",
            "function": "main",
            "line": 100,
            "message": "日志消息",
            "exception": "异常信息（可选）",
            "duration_ms": 123.45（可选）
        }
    """

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为 JSON

        Args:
            record: 日志记录

        Returns:
            JSON 格式的日志字符串
        """
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # 添加异常信息（如果有）
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        # 添加 duration 字段（如果存在）
        if hasattr(record, "duration"):
            log_entry["duration_ms"] = record.duration

        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(
    level: str = "INFO",
    log_format: str = "text",
    log_file: str | None = None,
) -> None:
    """配置日志系统

    Args:
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
        log_format: 日志格式 ("text" 或 "json")
        log_file: 日志文件路径（可选）
    """
    # 获取日志级别
    log_level = getattr(logging, level.upper(), logging.INFO)

    # 设置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清除现有处理器
    root_logger.handlers.clear()

    # 选择格式化器
    if log_format == "json":
        formatter: logging.Formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 文件处理器（可选）
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


__all__ = ["JSONFormatter", "setup_logging"]
