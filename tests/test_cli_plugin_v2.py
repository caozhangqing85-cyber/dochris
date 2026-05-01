"""补充测试 cli_plugin.py — 覆盖 cmd_plugin enable/disable 分支和 setup_plugin_parser"""

import argparse
from unittest.mock import MagicMock, patch

import pytest

from dochris.cli.cli_plugin import (
    cmd_plugin,
    setup_plugin_parser,
)
from dochris.plugin import get_plugin_manager, reset_plugin_manager


@pytest.fixture
def reset_pm():
    reset_plugin_manager()


class TestCmdPluginEnableDisable:
    """覆盖 cmd_plugin 入口的 enable/disable 子命令"""

    @patch("dochris.cli.cli_plugin._plugin_enable")
    def test_cmd_plugin_enable_dispatches(self, mock_enable, reset_pm):
        """enable 子命令正确分发"""
        mock_enable.return_value = 0
        args = argparse.Namespace(plugin_command="enable", name="test")

        result = cmd_plugin(args)

        assert result == 0
        mock_enable.assert_called_once_with(args)

    @patch("dochris.cli.cli_plugin._plugin_disable")
    def test_cmd_plugin_disable_dispatches(self, mock_disable, reset_pm):
        """disable 子命令正确分发"""
        mock_disable.return_value = 0
        args = argparse.Namespace(plugin_command="disable", name="test")

        result = cmd_plugin(args)

        assert result == 0
        mock_disable.assert_called_once_with(args)

    @patch("dochris.cli.cli_plugin._plugin_load")
    def test_cmd_plugin_load_dispatches(self, mock_load, reset_pm):
        """load 子命令正确分发"""
        mock_load.return_value = 0
        args = argparse.Namespace(plugin_command="load", path="/tmp/test.py")

        result = cmd_plugin(args)

        assert result == 0
        mock_load.assert_called_once_with(args)

    @patch("dochris.cli.cli_plugin.print")
    def test_cmd_plugin_unknown_command(self, mock_print, reset_pm):
        """未知子命令返回 1"""
        args = argparse.Namespace(plugin_command="unknown")

        result = cmd_plugin(args)

        assert result == 1


class TestSetupPluginParserFull:
    """覆盖 setup_plugin_parser 的 enable/disable/load 子命令解析"""

    def test_enable_subcommand(self):
        """enable 子命令解析"""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        setup_plugin_parser(subparsers)

        args = parser.parse_args(["plugin", "enable", "my_plugin"])
        assert args.command == "plugin"
        assert args.plugin_command == "enable"
        assert args.name == "my_plugin"

    def test_disable_subcommand(self):
        """disable 子命令解析"""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        setup_plugin_parser(subparsers)

        args = parser.parse_args(["plugin", "disable", "my_plugin"])
        assert args.plugin_command == "disable"
        assert args.name == "my_plugin"

    def test_load_subcommand(self):
        """load 子命令解析"""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        setup_plugin_parser(subparsers)

        args = parser.parse_args(["plugin", "load", "/path/to/plugin.py"])
        assert args.plugin_command == "load"
        assert args.path == "/path/to/plugin.py"
