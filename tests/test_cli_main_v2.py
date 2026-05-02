"""补充测试 cli/main.py — 覆盖 serve 和 unknown command 分支"""

from unittest.mock import patch

import pytest


class TestMainServeCommand:
    """覆盖 serve 子命令分发"""

    def test_serve_command_dispatches(self):
        from dochris.cli.main import main

        with patch("dochris.cli.main.cmd_serve", return_value=0) as mock_serve:
            with patch("sys.argv", ["kb", "serve"]):
                rc = main()

        assert rc == 0
        mock_serve.assert_called_once()

    def test_serve_with_host_port(self):
        from dochris.cli.main import main

        with patch("dochris.cli.main.cmd_serve", return_value=0) as mock_serve:
            with patch("sys.argv", ["kb", "serve", "--host", "127.0.0.1", "--port", "9000"]):
                rc = main()

        assert rc == 0
        args = mock_serve.call_args[0][0]
        assert args.host == "127.0.0.1"
        assert args.port == 9000


class TestMainUnknownCommand:
    """覆盖未知命令分支"""

    def test_unknown_command_returns_usage_error(self):
        """未知命令导致 SystemExit(2)"""
        from dochris.cli.main import main

        with patch("sys.argv", ["kb", "foobar"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 2
