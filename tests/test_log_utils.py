#!/usr/bin/env python3
"""测试 log_utils.py 日志工具模块"""

from __future__ import annotations

import json
import logging

from dochris.log_utils import (
    append_log_multi_to_markdown,
    append_log_to_file,
    append_log_to_markdown,
    get_default_workspace,
    get_logger,
    setup_logging,
)


class TestGetLogger:
    """测试 get_logger 函数"""

    def test_get_logger_returns_logger(self) -> None:
        """测试返回标准 Logger 实例"""
        result = get_logger("test_module")
        assert isinstance(result, logging.Logger)
        assert result.name == "test_module"

    def test_get_logger_same_name_same_instance(self) -> None:
        """测试相同名称返回相同实例"""
        logger1 = get_logger("test_same")
        logger2 = get_logger("test_same")
        assert logger1 is logger2


class TestGetDefaultWorkspace:
    """测试 get_default_workspace 函数"""

    def test_returns_path(self) -> None:
        """测试返回 Path 对象"""
        result = get_default_workspace()
        # 验证返回类型和基本结构
        assert result is not None
        assert "knowledge-base" in str(result) or result.name == "knowledge-base"


class TestSetupLogging:
    """测试 setup_logging 函数"""

    def test_setup_logging_basic(self) -> None:
        """测试基本日志配置"""
        root_logger = logging.getLogger()

        # 清除现有 handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        setup_logging(level=logging.INFO)

        assert root_logger.level == logging.INFO
        assert len(root_logger.handlers) >= 1

    def test_setup_logging_with_file(self, tmp_path) -> None:
        """测试带文件输出的日志配置"""
        log_file = tmp_path / "test.log"

        # 清除现有 handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        setup_logging(level=logging.DEBUG, log_file=log_file, also_console=False)

        # 验证文件 handler 被添加
        assert len(root_logger.handlers) >= 1
        assert log_file.exists()

        # 写入日志验证
        logger = get_logger("test_file")
        logger.info("test message")
        assert "test message" in log_file.read_text(encoding="utf-8")

    def test_setup_logging_console_only(self) -> None:
        """测试仅控制台输出"""
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        setup_logging(level=logging.WARNING, log_file=None, also_console=True)

        assert len(root_logger.handlers) >= 1
        assert isinstance(root_logger.handlers[0], logging.StreamHandler)


class TestAppendLogToFile:
    """测试 append_log_to_file 函数"""

    def test_append_log_creates_new_file(self, tmp_path) -> None:
        """测试追加日志创建新文件"""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        append_log_to_file(log_dir.parent, "test message", "system")

        files = list(log_dir.glob("system_*.json"))
        assert len(files) == 1

        content = files[0].read_text(encoding="utf-8")
        data = json.loads(content)
        assert len(data) == 1
        assert data[0]["message"] == "test message"
        assert data[0]["type"] == "system"

    def test_append_log_appends_to_existing(self, tmp_path) -> None:
        """测试追加日志到现有文件"""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # 第一次追加
        append_log_to_file(log_dir.parent, "first message", "compile")
        # 第二次追加
        append_log_to_file(log_dir.parent, "second message", "compile")

        files = list(log_dir.glob("compile_*.json"))
        assert len(files) == 1

        content = files[0].read_text(encoding="utf-8")
        data = json.loads(content)
        assert len(data) == 2
        assert data[0]["message"] == "first message"
        assert data[1]["message"] == "second message"

    def test_append_log_with_none_workspace(self, tmp_path) -> None:
        """测试 None workspace 使用默认路径"""
        # 使用 monkeypatch 修改默认工作区
        import dochris.log_utils

        original = dochris.log_utils.get_default_workspace
        dochris.log_utils.get_default_workspace = lambda: tmp_path

        try:
            append_log_to_file(None, "test message", "test")

            log_dir = tmp_path / "logs"
            files = list(log_dir.glob("test_*.json"))
            assert len(files) == 1
        finally:
            dochris.log_utils.get_default_workspace = original


class TestAppendLogToMarkdown:
    """测试 append_log_to_markdown 函数"""

    def test_append_creates_new_file(self, tmp_path) -> None:
        """测试追加日志创建新文件"""
        append_log_to_markdown(tmp_path, "ingest", "test detail")

        log_file = tmp_path / "log.md"
        assert log_file.exists()

        content = log_file.read_text(encoding="utf-8")
        assert "ingest" in content
        assert "test detail" in content

    def test_append_appends_to_existing(self, tmp_path) -> None:
        """测试追加到现有文件"""
        log_file = tmp_path / "log.md"

        # 第一次追加
        append_log_to_markdown(tmp_path, "compile", "detail1")
        # 第二次追加
        append_log_to_markdown(tmp_path, "promote", "detail2")

        content = log_file.read_text(encoding="utf-8")
        assert "compile" in content
        assert "promote" in content
        assert "detail1" in content
        assert "detail2" in content
        # 验证有两个条目
        assert content.count("## [") >= 2

    def test_append_with_none_workspace(self, tmp_path) -> None:
        """测试 None workspace 使用默认路径"""
        import dochris.log_utils

        original = dochris.log_utils.get_default_workspace
        dochris.log_utils.get_default_workspace = lambda: tmp_path

        try:
            append_log_to_markdown(None, "test_op", "test_detail")

            log_file = tmp_path / "log.md"
            assert log_file.exists()
            content = log_file.read_text(encoding="utf-8")
            assert "test_op" in content
        finally:
            dochris.log_utils.get_default_workspace = original


class TestAppendLogMultiToMarkdown:
    """测试 append_log_multi_to_markdown 函数"""

    def test_multi_append_creates_entries(self, tmp_path) -> None:
        """测试批量追加创建多条条目"""
        details = ["detail1", "detail2", "detail3"]

        append_log_multi_to_markdown(tmp_path, "batch", details)

        log_file = tmp_path / "log.md"
        content = log_file.read_text(encoding="utf-8")

        for detail in details:
            assert detail in content

    def test_multi_empty_list(self, tmp_path) -> None:
        """测试空列表不写入任何内容"""
        # 先创建一个已存在的日志文件
        log_file = tmp_path / "log.md"
        log_file.write_text("existing content", encoding="utf-8")

        # 调用空列表
        append_log_multi_to_markdown(tmp_path, "batch", [])

        # 文件内容不变（空列表不写入）
        content = log_file.read_text(encoding="utf-8")
        assert content == "existing content"
        assert "batch" not in content  # 没有新内容

    def test_multi_with_none_workspace(self, tmp_path) -> None:
        """测试 None workspace 使用默认路径"""
        import dochris.log_utils

        original = dochris.log_utils.get_default_workspace
        dochris.log_utils.get_default_workspace = lambda: tmp_path

        try:
            append_log_multi_to_markdown(None, "test_op", ["d1", "d2"])

            log_file = tmp_path / "log.md"
            assert log_file.exists()
            content = log_file.read_text(encoding="utf-8")
            assert "test_op" in content
            assert "d1" in content
            assert "d2" in content
        finally:
            dochris.log_utils.get_default_workspace = original
