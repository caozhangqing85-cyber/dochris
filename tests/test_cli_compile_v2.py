"""测试 cli/cli_compile.py 模块"""

import argparse
from unittest.mock import AsyncMock, patch


class TestCmdCompile:
    """测试 cmd_compile 函数"""

    def _make_args(
        self,
        named_limit=None,
        limit=10,
        concurrency=3,
        openrouter=False,
        dry_run=False,
    ):
        """构造 argparse.Namespace"""
        return argparse.Namespace(
            named_limit=named_limit,
            limit=limit,
            concurrency=concurrency,
            openrouter=openrouter,
            dry_run=dry_run,
        )

    @patch("dochris.cli.cli_compile.print")
    @patch(
        "dochris.phases.phase2_compilation.compile_all",
        new_callable=AsyncMock,
        return_value=None,
    )
    @patch("dochris.phases.phase2_compilation.setup_logging", return_value=None)
    def test_compile_success_default_args(self, mock_setup, mock_compile, mock_print):
        """正常编译，返回 0"""
        from dochris.cli.cli_compile import cmd_compile

        args = self._make_args()
        result = cmd_compile(args)
        assert result == 0
        mock_compile.assert_awaited_once()

    @patch("dochris.cli.cli_compile.print")
    @patch(
        "dochris.phases.phase2_compilation.compile_all",
        new_callable=AsyncMock,
        return_value=None,
    )
    @patch("dochris.phases.phase2_compilation.setup_logging", return_value=None)
    def test_compile_with_named_limit(self, mock_setup, mock_compile, mock_print):
        """named_limit 优先于 limit"""
        from dochris.cli.cli_compile import cmd_compile

        args = self._make_args(named_limit=5, limit=10)
        result = cmd_compile(args)
        assert result == 0
        _, kwargs = mock_compile.call_args
        assert kwargs["limit"] == 5

    @patch("dochris.cli.cli_compile.print")
    @patch(
        "dochris.phases.phase2_compilation.compile_all",
        new_callable=AsyncMock,
        return_value=None,
    )
    @patch("dochris.phases.phase2_compilation.setup_logging", return_value=None)
    def test_compile_named_limit_none_uses_limit(self, mock_setup, mock_compile, mock_print):
        """named_limit 为 None 时使用 limit"""
        from dochris.cli.cli_compile import cmd_compile

        args = self._make_args(named_limit=None, limit=20)
        result = cmd_compile(args)
        assert result == 0
        _, kwargs = mock_compile.call_args
        assert kwargs["limit"] == 20

    @patch("dochris.cli.cli_compile.print")
    @patch(
        "dochris.phases.phase2_compilation.compile_all",
        new_callable=AsyncMock,
        return_value=None,
    )
    @patch("dochris.phases.phase2_compilation.setup_logging", return_value=None)
    def test_compile_dry_run(self, mock_setup, mock_compile, mock_print):
        """dry-run 模式"""
        from dochris.cli.cli_compile import cmd_compile

        args = self._make_args(dry_run=True)
        result = cmd_compile(args)
        assert result == 0
        _, kwargs = mock_compile.call_args
        assert kwargs["dry_run"] is True

    @patch("dochris.cli.cli_compile.print")
    @patch(
        "dochris.phases.phase2_compilation.compile_all",
        new_callable=AsyncMock,
        side_effect=RuntimeError("API error"),
    )
    @patch("dochris.phases.phase2_compilation.setup_logging", return_value=None)
    def test_compile_failure_returns_1(self, mock_setup, mock_compile, mock_print):
        """编译异常返回 1"""
        from dochris.cli.cli_compile import cmd_compile

        args = self._make_args()
        result = cmd_compile(args)
        assert result == 1

    @patch("dochris.cli.cli_compile.print")
    @patch(
        "dochris.phases.phase2_compilation.compile_all",
        new_callable=AsyncMock,
        return_value=None,
    )
    @patch("dochris.phases.phase2_compilation.setup_logging", return_value=None)
    def test_compile_passes_openrouter(self, mock_setup, mock_compile, mock_print):
        """传递 openrouter 参数"""
        from dochris.cli.cli_compile import cmd_compile

        args = self._make_args(openrouter=True)
        result = cmd_compile(args)
        assert result == 0
        _, kwargs = mock_compile.call_args
        assert kwargs["use_openrouter"] is True

    @patch("dochris.cli.cli_compile.print")
    @patch(
        "dochris.phases.phase2_compilation.compile_all",
        new_callable=AsyncMock,
        return_value=None,
    )
    @patch("dochris.phases.phase2_compilation.setup_logging", return_value=None)
    def test_compile_passes_concurrency(self, mock_setup, mock_compile, mock_print):
        """传递并发数参数"""
        from dochris.cli.cli_compile import cmd_compile

        args = self._make_args(concurrency=5)
        result = cmd_compile(args)
        assert result == 0
        _, kwargs = mock_compile.call_args
        assert kwargs["max_concurrent"] == 5
