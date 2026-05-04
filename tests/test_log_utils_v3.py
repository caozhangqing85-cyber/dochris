"""日志工具模块测试"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from dochris.log_utils import (
    append_log_multi_to_markdown,
    append_log_to_file,
    append_log_to_markdown,
    get_default_workspace,
    get_logger,
    setup_logging,
)

# ── get_logger ─────────────────────────────────────────────────


class TestGetLogger:
    """获取 logger 实例"""

    def test_returns_logger(self):
        """返回 Logger 实例"""
        lg = get_logger("test.module")
        assert isinstance(lg, logging.Logger)

    def test_logger_name(self):
        """logger 名称正确"""
        lg = get_logger("my.custom.logger")
        assert lg.name == "my.custom.logger"

    def test_same_name_same_instance(self):
        """同名 logger 返回同一实例"""
        lg1 = get_logger("same.name")
        lg2 = get_logger("same.name")
        assert lg1 is lg2


# ── get_default_workspace ──────────────────────────────────────


class TestGetDefaultWorkspace:
    """获取默认工作区路径"""

    def test_returns_path(self):
        """返回 Path 实例"""
        result = get_default_workspace()
        assert isinstance(result, Path)

    def test_contains_knowledge_base(self):
        """路径包含 knowledge-base"""
        result = get_default_workspace()
        assert "knowledge-base" in str(result)


# ── setup_logging ──────────────────────────────────────────────


class TestSetupLogging:
    """配置日志系统"""

    def test_console_handler(self, tmp_path):
        """默认添加控制台 handler"""
        # 清除 root logger 的 handlers 以避免干扰
        root = logging.getLogger()
        original_handlers = root.handlers[:]
        try:
            root.handlers.clear()
            setup_logging()
            assert any(isinstance(h, logging.StreamHandler) for h in root.handlers)
        finally:
            root.handlers = original_handlers

    def test_file_handler(self, tmp_path):
        """指定日志文件时添加 FileHandler"""
        root = logging.getLogger()
        original_handlers = root.handlers[:]
        try:
            root.handlers.clear()
            log_file = tmp_path / "test.log"
            setup_logging(log_file=log_file)
            assert any(isinstance(h, logging.FileHandler) for h in root.handlers)
        finally:
            root.handlers = original_handlers

    def test_no_console_when_disabled(self, tmp_path):
        """禁用控制台时不添加 StreamHandler"""
        root = logging.getLogger()
        original_handlers = root.handlers[:]
        original_level = root.level
        try:
            root.handlers.clear()
            setup_logging(also_console=False)
            assert not any(isinstance(h, logging.StreamHandler) for h in root.handlers)
        finally:
            root.handlers = original_handlers
            root.level = original_level

    def test_custom_level(self, tmp_path):
        """自定义日志级别"""
        root = logging.getLogger()
        original_handlers = root.handlers[:]
        original_level = root.level
        try:
            root.handlers.clear()
            setup_logging(level=logging.DEBUG)
            assert root.level == logging.DEBUG
        finally:
            root.handlers = original_handlers
            root.level = original_level


# ── append_log_to_file ─────────────────────────────────────────


class TestAppendLogToFile:
    """追加日志到 JSON 文件"""

    def test_creates_log_file(self, tmp_path):
        """首次写入创建日志文件"""
        append_log_to_file(tmp_path, "first message", log_type="test")
        log_dir = tmp_path / "logs"
        log_files = list(log_dir.glob("test_*.json"))
        assert len(log_files) == 1

    def test_log_entry_structure(self, tmp_path):
        """日志条目包含 timestamp、type、message"""
        append_log_to_file(tmp_path, "hello", log_type="system")
        log_file = next((tmp_path / "logs").glob("system_*.json"))
        data = json.loads(log_file.read_text(encoding="utf-8"))
        entry = data[0]
        assert "timestamp" in entry
        assert entry["type"] == "system"
        assert entry["message"] == "hello"

    def test_appends_to_existing(self, tmp_path):
        """追加到已有日志文件"""
        append_log_to_file(tmp_path, "msg1", log_type="test")
        append_log_to_file(tmp_path, "msg2", log_type="test")
        log_file = next((tmp_path / "logs").glob("test_*.json"))
        data = json.loads(log_file.read_text(encoding="utf-8"))
        assert len(data) == 2
        assert data[0]["message"] == "msg1"
        assert data[1]["message"] == "msg2"

    def test_handles_corrupted_log_file(self, tmp_path):
        """损坏的日志文件被跳过并继续写入"""
        from datetime import datetime

        logs_dir = tmp_path / "logs"
        logs_dir.mkdir(parents=True)
        # 使用与函数相同的文件名格式
        date_str = datetime.now().strftime("%Y%m%d")
        log_file = logs_dir / f"test_corrupted_{date_str}.json"
        log_file.write_text("{broken", encoding="utf-8")
        # 不应抛异常
        append_log_to_file(tmp_path, "recovery message", log_type="test_corrupted")
        # 损坏的 JSON 被跳过，新日志写入数组
        data = json.loads(log_file.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert any(e["message"] == "recovery message" for e in data)

    def test_none_workspace_uses_default(self):
        """workspace 为 None 时使用默认路径"""
        # 不检查默认路径是否存在（可能不存在），只确保不抛异常
        append_log_to_file(None, "test with none workspace", log_type="pytest")


# ── append_log_to_markdown ─────────────────────────────────────


class TestAppendLogToMarkdown:
    """追加日志到 Markdown 文件"""

    def test_creates_log_md(self, tmp_path):
        """创建 log.md"""
        append_log_to_markdown(tmp_path, "ingest", "test.pdf")
        assert (tmp_path / "log.md").exists()

    def test_entry_format(self, tmp_path):
        """日志条目格式正确"""
        append_log_to_markdown(tmp_path, "compile", "result ok")
        content = (tmp_path / "log.md").read_text(encoding="utf-8")
        assert "## [" in content
        assert "compile" in content
        assert "result ok" in content

    def test_appends_multiple(self, tmp_path):
        """追加多条日志"""
        append_log_to_markdown(tmp_path, "ingest", "a.pdf")
        append_log_to_markdown(tmp_path, "compile", "b.pdf")
        content = (tmp_path / "log.md").read_text(encoding="utf-8")
        assert content.count("## [") == 2


# ── append_log_multi_to_markdown ───────────────────────────────


class TestAppendLogMultiToMarkdown:
    """批量追加日志到 Markdown"""

    def test_multiple_details(self, tmp_path):
        """同一操作的多条 detail"""
        append_log_multi_to_markdown(
            tmp_path, "batch_ingest", ["file1.pdf", "file2.pdf", "file3.pdf"]
        )
        content = (tmp_path / "log.md").read_text(encoding="utf-8")
        assert "file1.pdf" in content
        assert "file2.pdf" in content
        assert "file3.pdf" in content
        assert content.count("## [") == 3

    def test_empty_details(self, tmp_path):
        """空 details 列表仍会创建文件但不写入条目"""
        append_log_multi_to_markdown(tmp_path, "noop", [])
        # 函数会打开文件但写入空内容（空循环），文件可能存在但为空
        log_path = tmp_path / "log.md"
        if log_path.exists():
            assert log_path.read_text(encoding="utf-8") == ""
        else:
            assert not log_path.exists()
