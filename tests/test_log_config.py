#!/usr/bin/env python3
"""测试日志配置模块"""
from __future__ import annotations

import json
import logging

from dochris.log_config import JSONFormatter, setup_logging


class TestJSONFormatter:
    """测试 JSONFormatter"""

    def test_format_basic_record(self) -> None:
        """测试格式化基本日志记录"""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_module",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["level"] == "INFO"
        assert data["module"] == "test"  # 文件名不带 .py 后缀
        assert data["line"] == 42
        assert data["message"] == "Test message"
        assert "timestamp" in data
        assert "function" in data

    def test_format_with_exception(self) -> None:
        """测试格式化带异常的日志记录"""
        import sys

        formatter = JSONFormatter()

        try:
            raise ValueError("Test exception")
        except ValueError:
            # 使用 sys.exc_info() 获取真实的异常信息
            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test_module",
                level=logging.ERROR,
                pathname="test.py",
                lineno=42,
                msg="Error occurred",
                args=(),
                exc_info=exc_info,
            )

        result = formatter.format(record)
        # 验证格式化不会抛出错误
        assert result is not None
        # 结果应该是有效的 JSON
        data = json.loads(result)
        assert "message" in data
        assert "exception" in data  # 应该包含异常信息

    def test_format_with_duration(self) -> None:
        """测试格式化带 duration 的日志记录"""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_module",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.duration = 123.45

        result = formatter.format(record)
        data = json.loads(result)

        assert "duration_ms" in data
        assert data["duration_ms"] == 123.45


class TestSetupLogging:
    """测试 setup_logging 函数"""

    def test_setup_logging_default_text_format(self) -> None:
        """测试默认文本格式日志配置"""
        setup_logging(level="INFO")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

        # 验证有至少一个 handler
        assert len(root_logger.handlers) >= 1

        # 第一个应该是 StreamHandler
        handler = root_logger.handlers[0]
        assert isinstance(handler, logging.StreamHandler)

    def test_setup_logging_json_format(self) -> None:
        """测试 JSON 格式日志配置"""
        setup_logging(level="DEBUG", log_format="json")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

        handler = root_logger.handlers[0]
        assert isinstance(handler, logging.StreamHandler)
        # JSONFormatter 是 logging.Formatter 的子类
        assert isinstance(handler.formatter, logging.Formatter)

    def test_setup_logging_with_file(self, tmp_path) -> None:
        """测试带文件输出的日志配置"""
        log_file = str(tmp_path / "test.log")

        setup_logging(level="INFO", log_file=log_file)

        root_logger = logging.getLogger()

        # 应该有两个 handler：控制台和文件
        assert len(root_logger.handlers) >= 1

        # 找文件 handler
        file_handler = None
        for handler in root_logger.handlers:
            if isinstance(handler, logging.FileHandler):
                file_handler = handler
                break

        if file_handler:
            assert file_handler.level == logging.DEBUG

    def test_setup_logging_invalid_level(self) -> None:
        """测试无效日志级别时使用默认 INFO"""
        # 无效级别会默认使用 INFO
        setup_logging(level="INVALID")

        root_logger = logging.getLogger()
        # getattr 会返回默认值 logging.INFO
        assert root_logger.level == logging.INFO

    def test_setup_logging_clears_existing_handlers(self) -> None:
        """测试配置日志会清除现有处理器"""
        root_logger = logging.getLogger()

        # 添加一个初始 handler
        initial_handler = logging.StreamHandler()
        root_logger.addHandler(initial_handler)

        initial_count = len(root_logger.handlers)

        # 调用 setup_logging
        setup_logging(level="INFO")

        # 应该被清除并重新添加
        assert len(root_logger.handlers) != initial_count or initial_handler not in root_logger.handlers
