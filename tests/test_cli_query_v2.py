"""测试 cli/cli_query.py 模块"""

import argparse
from unittest.mock import MagicMock, patch


class TestCmdQuery:
    """测试 cmd_query 函数"""

    def _make_args(self, query=None, mode=None, top_k=None):
        return argparse.Namespace(query=query, mode=mode, top_k=top_k)

    @patch("dochris.phases.phase3_query.print_result")
    @patch(
        "dochris.phases.phase3_query.query",
        return_value={"answer": "test answer"},
    )
    @patch("dochris.phases.phase3_query.setup_logging", return_value=MagicMock())
    def test_query_with_answer_returns_0(self, mock_setup, mock_query, mock_print_result):
        """查询有结果返回 0"""
        from dochris.cli.cli_query import cmd_query

        args = self._make_args(query="test query", mode="combined", top_k=5)
        result = cmd_query(args)
        assert result == 0

    @patch("dochris.phases.phase3_query.print_result")
    @patch(
        "dochris.phases.phase3_query.query",
        return_value={},
    )
    @patch("dochris.phases.phase3_query.setup_logging", return_value=MagicMock())
    def test_query_no_answer_returns_1(self, mock_setup, mock_query, mock_print_result):
        """查询无结果返回 1"""
        from dochris.cli.cli_query import cmd_query

        args = self._make_args(query="test query")
        result = cmd_query(args)
        assert result == 1

    @patch("dochris.phases.phase3_query.interactive_mode")
    @patch("dochris.phases.phase3_query.setup_logging", return_value=MagicMock())
    def test_query_interactive_mode(self, mock_setup, mock_interactive):
        """无 query 参数进入交互模式"""
        from dochris.cli.cli_query import cmd_query

        args = self._make_args(query=None)
        result = cmd_query(args)
        assert result == 0
        mock_interactive.assert_called_once()

    @patch("dochris.phases.phase3_query.print_result")
    @patch(
        "dochris.phases.phase3_query.query",
        return_value={"answer": "result"},
    )
    @patch("dochris.phases.phase3_query.setup_logging", return_value=MagicMock())
    def test_query_default_mode_is_combined(self, mock_setup, mock_query, mock_print_result):
        """默认 mode 为 combined"""
        from dochris.cli.cli_query import cmd_query

        args = self._make_args(query="test", mode=None, top_k=None)
        result = cmd_query(args)
        assert result == 0
        _, kwargs = mock_query.call_args
        assert kwargs["mode"] == "combined"
        assert kwargs["top_k"] == 5

    @patch("dochris.phases.phase3_query.print_result")
    @patch(
        "dochris.phases.phase3_query.query",
        return_value={"answer": "vector result"},
    )
    @patch("dochris.phases.phase3_query.setup_logging", return_value=MagicMock())
    def test_query_custom_mode_and_topk(self, mock_setup, mock_query, mock_print_result):
        """自定义 mode 和 top_k"""
        from dochris.cli.cli_query import cmd_query

        args = self._make_args(query="test", mode="vector", top_k=10)
        result = cmd_query(args)
        assert result == 0
        _, kwargs = mock_query.call_args
        assert kwargs["mode"] == "vector"
        assert kwargs["top_k"] == 10

    @patch("dochris.phases.phase3_query.print_result")
    @patch(
        "dochris.phases.phase3_query.query",
        return_value={"answer": "yes", "sources": []},
    )
    @patch("dochris.phases.phase3_query.setup_logging", return_value=MagicMock())
    def test_query_with_answer_field_present(self, mock_setup, mock_query, mock_print_result):
        """answer 字段存在返回 0"""
        from dochris.cli.cli_query import cmd_query

        args = self._make_args(query="test")
        result = cmd_query(args)
        assert result == 0
