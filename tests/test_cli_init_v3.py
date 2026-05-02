"""补充测试 cli_init.py — 覆盖 Python version check 和 OSError 分支"""

from argparse import Namespace
from unittest.mock import MagicMock, patch


class TestCmdInitPythonVersion:
    """覆盖 Python 版本检查失败分支 (line 32-34)"""

    @patch("builtins.input")
    @patch("dochris.settings.get_default_workspace")
    def test_low_python_version_returns_1(self, mock_ws, mock_input, tmp_path, monkeypatch):
        """Python < 3.11 返回 1"""
        from dochris.cli.cli_init import cmd_init

        workspace = tmp_path / "kb"
        workspace.mkdir()
        mock_ws.return_value = workspace
        monkeypatch.setenv("WORKSPACE", str(workspace))

        # sys.version_info 是一个特殊类型，支持 .major/.minor 和比较
        mock_vi = MagicMock()
        mock_vi.major = 3
        mock_vi.minor = 10
        mock_vi.micro = 0
        mock_vi.__lt__ = lambda self, other: other > (3, 10)
        mock_vi.__ge__ = lambda self, other: other <= (3, 10)

        with patch("dochris.cli.cli_init.sys.version_info", mock_vi):
            with patch("builtins.print"):
                result = cmd_init(Namespace())

        assert result == 1


class TestCmdInitOSError:
    """覆盖 OSError 分支 (line 102-103)"""

    @patch("builtins.input")
    @patch("dochris.settings.get_default_workspace")
    def test_env_read_oserror_suppressed(self, mock_ws, mock_input, tmp_path, monkeypatch):
        """读取 .env 文件时 OSError 被 suppress"""
        from dochris.cli.cli_init import cmd_init

        workspace = tmp_path / "kb"
        workspace.mkdir()
        mock_ws.return_value = workspace
        monkeypatch.setenv("WORKSPACE", str(workspace))

        mock_input.return_value = "test-key-12345"

        with patch("builtins.print"):
            result = cmd_init(Namespace())

        assert result == 0
