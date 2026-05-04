"""Web 共享工具模块测试"""

from __future__ import annotations

from pathlib import Path

from dochris.web.utils import (
    sanitize_path,
)

# ── sanitize_path ──────────────────────────────────────────────


class TestSanitizePath:
    """路径脱敏：只显示最后两级目录"""

    def test_short_path(self):
        """短路径返回文件名"""
        assert sanitize_path(Path("file.txt")) == "file.txt"

    def test_two_level_path(self):
        """两级路径完整显示"""
        assert sanitize_path(Path("/home/user")) == str(Path("home/user"))

    def test_deep_path(self):
        """深层路径只显示最后两级"""
        result = sanitize_path(Path("/a/b/c/d/file.txt"))
        assert result == str(Path("d/file.txt"))

    def test_absolute_path(self):
        """绝对路径脱敏"""
        result = sanitize_path(Path("/home/admin/.openclaw/knowledge-base"))
        parts = result.split("/")
        assert len(parts) <= 2
