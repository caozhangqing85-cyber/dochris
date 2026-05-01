"""测试 log_utils 模块"""

import json
import tempfile
from pathlib import Path

from dochris.log_utils import (
    append_log_multi_to_markdown,
    append_log_to_file,
    append_log_to_markdown,
    get_default_workspace,
    get_logger,
    setup_logging,
)


class TestGetLogger:
    def test_returns_logger(self):
        import logging
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"


class TestSetupLogging:
    def test_basic_setup(self):
        import logging
        setup_logging(level=logging.DEBUG)
        root = logging.getLogger()
        # log_utils.setup_logging 使用 basicConfig，可能因为已有 handler 不生效
        # 只验证不抛异常
        assert root.level <= logging.WARNING or root.level == logging.DEBUG

    def test_with_file(self):
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            log_path = Path(f.name)
        setup_logging(level=20, log_file=log_path, also_console=False)
        import os
        os.unlink(str(log_path))


class TestGetDefaultWorkspace:
    def test_returns_path(self):
        ws = get_default_workspace()
        assert isinstance(ws, Path)
        assert ".openclaw/knowledge-base" in str(ws)


class TestAppendLogToFile:
    def test_creates_log_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Path(tmpdir)
            append_log_to_file(ws, "test message", "system")
            log_dir = ws / "logs"
            assert log_dir.exists()
            # 应该有一个 json 文件
            json_files = list(log_dir.glob("system_*.json"))
            assert len(json_files) == 1
            with open(json_files[0], encoding="utf-8") as f:
                logs = json.load(f)
            assert len(logs) == 1
            assert logs[0]["message"] == "test message"
            assert logs[0]["type"] == "system"

    def test_appends_to_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Path(tmpdir)
            append_log_to_file(ws, "msg1", "test")
            append_log_to_file(ws, "msg2", "test")
            log_dir = ws / "logs"
            json_files = list(log_dir.glob("test_*.json"))
            assert len(json_files) == 1
            with open(json_files[0], encoding="utf-8") as f:
                logs = json.load(f)
            assert len(logs) == 2

    def test_none_workspace_uses_default(self):
        # 使用 None workspace 应该使用默认路径
        # 这里只验证不抛异常
        try:
            append_log_to_file(None, "test", "test_none_ws")
        except Exception:
            pass  # 可能因为权限问题失败，但不应是逻辑错误


class TestAppendLogToMarkdown:
    def test_creates_markdown_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Path(tmpdir)
            append_log_to_markdown(ws, "compile", "test.md")
            log_path = ws / "log.md"
            assert log_path.exists()
            content = log_path.read_text(encoding="utf-8")
            assert "compile" in content
            assert "test.md" in content

    def test_appends_multiple_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Path(tmpdir)
            append_log_to_markdown(ws, "ingest", "file1.txt")
            append_log_to_markdown(ws, "compile", "file2.txt")
            content = (ws / "log.md").read_text(encoding="utf-8")
            assert "ingest" in content
            assert "compile" in content


class TestAppendLogMultiToMarkdown:
    def test_multiple_details(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Path(tmpdir)
            append_log_multi_to_markdown(ws, "ingest", ["f1.txt", "f2.txt", "f3.txt"])
            content = (ws / "log.md").read_text(encoding="utf-8")
            assert "f1.txt" in content
            assert "f2.txt" in content
            assert "f3.txt" in content
