"""补充测试 cli_init.py — 覆盖 OSError 分支"""

from argparse import Namespace
from unittest.mock import patch


class TestCmdInitErrorBranches:
    """覆盖 cli_init.py 中未覆盖的错误分支"""

    @patch("builtins.input")
    @patch("dochris.settings.get_default_workspace")
    def test_oserror_on_mkdir_returns_1(self, mock_ws, mock_input, tmp_path, monkeypatch):
        """创建目录 OSError 返回 1"""
        from dochris.cli.cli_init import cmd_init

        workspace = tmp_path / "kb"
        mock_ws.return_value = workspace
        monkeypatch.setenv("WORKSPACE", str(workspace))

        mock_input.return_value = "test-key"

        with patch("pathlib.Path.mkdir", side_effect=OSError("permission denied")):
            result = cmd_init(Namespace())

        assert result == 1
