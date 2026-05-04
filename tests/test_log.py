#!/usr/bin/env python3
"""测试日志模块"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from dochris.log import append_log, append_log_multi, get_default_workspace


class TestLogModule:
    """测试 log.py 模块"""

    def test_get_default_workspace(self) -> None:
        """测试获取默认工作区路径"""
        mock_settings = MagicMock()
        mock_settings.workspace = "/test/workspace"

        with patch("dochris.log.get_settings", return_value=mock_settings):
            result = get_default_workspace()
            assert result == "/test/workspace"

    def test_append_log(self) -> None:
        """测试追加单条日志"""
        mock_settings = MagicMock()
        mock_settings.workspace = "/test/workspace"

        with patch("dochris.log.get_settings", return_value=mock_settings):
            with patch("dochris.log.append_log_to_markdown") as mock_append:
                append_log("/test/workspace", "ingest", "test detail")

                mock_append.assert_called_once()
                call_args = mock_append.call_args
                assert call_args[0][1] == "ingest"
                assert call_args[0][2] == "test detail"

    def test_append_log_multi(self) -> None:
        """测试批量追加日志"""
        with patch("dochris.log.append_log_multi_to_markdown") as mock_append:
            append_log_multi("/test/workspace", "compile", ["detail1", "detail2"])

            mock_append.assert_called_once()
            call_args = mock_append.call_args
            assert call_args[0][1] == "compile"
            assert call_args[0][2] == ["detail1", "detail2"]
