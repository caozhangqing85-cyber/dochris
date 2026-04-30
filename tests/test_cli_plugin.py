"""
测试 CLI 插件命令 (cli_plugin.py)
"""

import argparse
from unittest.mock import patch

import pytest

from dochris.cli.cli_plugin import (
    _plugin_disable,
    _plugin_enable,
    _plugin_info,
    _plugin_list,
    _plugin_load,
    _print_plugin_help,
    cmd_plugin,
    setup_plugin_parser,
)
from dochris.plugin import reset_plugin_manager


@pytest.fixture
def reset_pm():
    """每个测试前重置插件管理器"""
    reset_plugin_manager()


class TestPrintPluginHelp:
    """测试 _print_plugin_help 函数"""

    @patch("dochris.cli.cli_plugin.print")
    def test_print_plugin_help(self, mock_print):
        """测试打印插件帮助"""
        _print_plugin_help()

        # 验证调用了 print
        assert mock_print.call_count > 0

        # 验证输出包含关键内容
        calls = [str(call) for call in mock_print.call_args_list]
        output = " ".join(calls)
        assert "list" in output
        assert "info" in output
        assert "enable" in output
        assert "disable" in output
        assert "load" in output


class TestPluginList:
    """测试 _plugin_list 函数"""

    @patch("dochris.cli.cli_plugin.print")
    def test_plugin_list_empty(self, mock_print, reset_pm):
        """测试没有插件时的输出"""
        args = argparse.Namespace()
        result = _plugin_list(args)

        assert result == 0

        # 验证打印了"没有插件"消息
        calls = [str(call) for call in mock_print.call_args_list]
        output = " ".join(calls)
        assert "没有" in output or "插件" in output

    @patch("dochris.cli.cli_plugin.print")
    def test_plugin_list_with_plugins(self, mock_print, reset_pm):
        """测试有插件时的输出"""
        from dochris.plugin import get_plugin_manager

        pm = get_plugin_manager()

        # 注册测试插件（使用 _register_module 会更新 _plugin_order）
        def hook1():
            pass

        def hook2():
            pass

        pm._register_module("test_plugin1", None, [("hook_a", hook1)])
        pm._register_module("test_plugin2", None, [("hook_b", hook2)])
        pm._plugins["test_plugin1"]["enabled"] = True
        pm._plugins["test_plugin2"]["enabled"] = False

        args = argparse.Namespace()
        result = _plugin_list(args)

        assert result == 0

        # 验证输出包含插件信息
        calls = [str(call) for call in mock_print.call_args_list]
        output = " ".join(calls)
        assert "test_plugin1" in output
        assert "test_plugin2" in output
        assert "已注册" in output or "2" in output


class TestPluginInfo:
    """测试 _plugin_info 函数"""

    @patch("dochris.cli.cli_plugin.print")
    def test_plugin_info_missing_name(self, mock_print, reset_pm):
        """测试缺少插件名称"""
        args = argparse.Namespace(name=None)

        result = _plugin_info(args)

        assert result == 1

        # 验证错误消息
        calls = [str(call) for call in mock_print.call_args_list]
        output = " ".join(calls)
        assert "缺少" in output or "插件名称" in output

    @patch("dochris.cli.cli_plugin.print")
    def test_plugin_info_nonexistent(self, mock_print, reset_pm):
        """测试查看不存在的插件"""
        args = argparse.Namespace(name="nonexistent")

        result = _plugin_info(args)

        assert result == 1

        # 验证错误消息
        calls = [str(call) for call in mock_print.call_args_list]
        output = " ".join(calls)
        assert "不存在" in output or "nonexistent" in output

    @patch("dochris.cli.cli_plugin.print")
    def test_plugin_info_valid(self, mock_print, reset_pm):
        """测试查看有效插件详情"""
        from dochris.plugin import get_plugin_manager

        pm = get_plugin_manager()

        def hook_func():
            pass

        pm._register_module("test_plugin", None, [("test_hook", hook_func)])
        pm._plugins["test_plugin"]["enabled"] = True

        args = argparse.Namespace(name="test_plugin")

        result = _plugin_info(args)

        assert result == 0

        # 验证输出包含插件详情
        calls = [str(call) for call in mock_print.call_args_list]
        output = " ".join(calls)
        assert "test_plugin" in output
        assert "test_hook" in output


class TestPluginEnable:
    """测试 _plugin_enable 函数"""

    @patch("dochris.cli.cli_plugin.print")
    def test_plugin_enable_missing_name(self, mock_print, reset_pm):
        """测试缺少插件名称"""
        args = argparse.Namespace(name=None)

        result = _plugin_enable(args)

        assert result == 1

        # 验证错误消息
        calls = [str(call) for call in mock_print.call_args_list]
        output = " ".join(calls)
        assert "缺少" in output or "插件名称" in output

    @patch("dochris.cli.cli_plugin.print")
    def test_plugin_enable_nonexistent(self, mock_print, reset_pm):
        """测试启用不存在的插件"""
        args = argparse.Namespace(name="nonexistent")

        result = _plugin_enable(args)

        assert result == 1

        # 验证错误消息
        calls = [str(call) for call in mock_print.call_args_list]
        output = " ".join(calls)
        assert "不存在" in output or "nonexistent" in output

    @patch("dochris.cli.cli_plugin.print")
    def test_plugin_enable_already_enabled(self, mock_print, reset_pm):
        """测试启用已启用的插件"""
        from dochris.plugin import get_plugin_manager

        pm = get_plugin_manager()

        def hook_func():
            pass

        pm._register_module("test_plugin", None, [("test_hook", hook_func)])
        pm._plugins["test_plugin"]["enabled"] = True

        args = argparse.Namespace(name="test_plugin")

        result = _plugin_enable(args)

        assert result == 0

        # 验证警告消息
        calls = [str(call) for call in mock_print.call_args_list]
        output = " ".join(calls)
        assert "已启用" in output or "test_plugin" in output

    @patch("dochris.cli.cli_plugin.print")
    def test_plugin_enable_success(self, mock_print, reset_pm):
        """测试成功启用插件"""
        from dochris.plugin import get_plugin_manager

        pm = get_plugin_manager()

        def hook_func():
            pass

        pm._register_module("test_plugin", None, [("test_hook", hook_func)])
        pm._plugins["test_plugin"]["enabled"] = False

        args = argparse.Namespace(name="test_plugin")

        result = _plugin_enable(args)

        assert result == 0

        # 验证成功消息
        calls = [str(call) for call in mock_print.call_args_list]
        output = " ".join(calls)
        assert "已启用" in output or "test_plugin" in output

        # 验证插件确实被启用
        assert pm.is_enabled("test_plugin") is True


class TestPluginDisable:
    """测试 _plugin_disable 函数"""

    @patch("dochris.cli.cli_plugin.print")
    def test_plugin_disable_missing_name(self, mock_print, reset_pm):
        """测试缺少插件名称"""
        args = argparse.Namespace(name=None)

        result = _plugin_disable(args)

        assert result == 1

        # 验证错误消息
        calls = [str(call) for call in mock_print.call_args_list]
        output = " ".join(calls)
        assert "缺少" in output or "插件名称" in output

    @patch("dochris.cli.cli_plugin.print")
    def test_plugin_disable_nonexistent(self, mock_print, reset_pm):
        """测试禁用不存在的插件"""
        args = argparse.Namespace(name="nonexistent")

        result = _plugin_disable(args)

        assert result == 1

        # 验证错误消息
        calls = [str(call) for call in mock_print.call_args_list]
        output = " ".join(calls)
        assert "不存在" in output or "nonexistent" in output

    @patch("dochris.cli.cli_plugin.print")
    def test_plugin_disable_already_disabled(self, mock_print, reset_pm):
        """测试禁用已禁用的插件"""
        from dochris.plugin import get_plugin_manager

        pm = get_plugin_manager()

        def hook_func():
            pass

        pm._register_module("test_plugin", None, [("test_hook", hook_func)])
        pm._plugins["test_plugin"]["enabled"] = False

        args = argparse.Namespace(name="test_plugin")

        result = _plugin_disable(args)

        assert result == 0

        # 验证警告消息
        calls = [str(call) for call in mock_print.call_args_list]
        output = " ".join(calls)
        assert "已禁用" in output or "test_plugin" in output

    @patch("dochris.cli.cli_plugin.print")
    def test_plugin_disable_success(self, mock_print, reset_pm):
        """测试成功禁用插件"""
        from dochris.plugin import get_plugin_manager

        pm = get_plugin_manager()

        def hook_func():
            pass

        pm._register_module("test_plugin", None, [("test_hook", hook_func)])
        pm._plugins["test_plugin"]["enabled"] = True

        args = argparse.Namespace(name="test_plugin")

        result = _plugin_disable(args)

        assert result == 0

        # 验证成功消息
        calls = [str(call) for call in mock_print.call_args_list]
        output = " ".join(calls)
        assert "已禁用" in output or "test_plugin" in output

        # 验证插件确实被禁用
        assert pm.is_enabled("test_plugin") is False


class TestPluginLoad:
    """测试 _plugin_load 函数"""

    @patch("dochris.cli.cli_plugin.print")
    def test_plugin_load_missing_path(self, mock_print, reset_pm):
        """测试缺少插件路径"""
        args = argparse.Namespace(path=None)

        result = _plugin_load(args)

        assert result == 1

        # 验证错误消息
        calls = [str(call) for call in mock_print.call_args_list]
        output = " ".join(calls)
        assert "缺少" in output or "路径" in output

    @patch("dochris.cli.cli_plugin.print")
    def test_plugin_load_nonexistent_file(self, mock_print, reset_pm):
        """测试加载不存在的文件"""
        args = argparse.Namespace(path="/nonexistent/plugin.py")

        result = _plugin_load(args)

        assert result == 1

        # 验证错误消息
        calls = [str(call) for call in mock_print.call_args_list]
        output = " ".join(calls)
        assert "不存在" in output

    @patch("dochris.cli.cli_plugin.print")
    def test_plugin_load_invalid_extension(self, mock_print, reset_pm, tmp_path):
        """测试加载非 .py 文件"""
        test_file = tmp_path / "plugin.txt"
        test_file.write_text("not a python file")

        args = argparse.Namespace(path=str(test_file))

        result = _plugin_load(args)

        assert result == 1

        # 验证错误消息
        calls = [str(call) for call in mock_print.call_args_list]
        output = " ".join(calls)
        assert "Python" in output or ".py" in output

    @patch("dochris.cli.cli_plugin.print")
    def test_plugin_load_no_hookimpl(self, mock_print, reset_pm, tmp_path):
        """测试加载没有 hookimpl 的文件"""
        plugin_file = tmp_path / "empty_plugin.py"
        plugin_file.write_text(
            """
# 没有hookimpl的插件
def regular_function():
    pass
""",
            encoding="utf-8",
        )

        args = argparse.Namespace(path=str(plugin_file))

        result = _plugin_load(args)

        assert result == 1

        # 验证错误消息
        calls = [str(call) for call in mock_print.call_args_list]
        output = " ".join(calls)
        assert "未发现" in output or "hookimpl" in output

    @patch("dochris.cli.cli_plugin.print")
    def test_plugin_load_success(self, mock_print, reset_pm, tmp_path):
        """测试成功加载插件"""
        plugin_file = tmp_path / "test_plugin.py"
        plugin_file.write_text(
            """
# 测试插件

def test_hook():
    return "test"

test_hook._is_hookimpl = True
""",
            encoding="utf-8",
        )

        args = argparse.Namespace(path=str(plugin_file))

        result = _plugin_load(args)

        assert result == 0

        # 验证成功消息
        calls = [str(call) for call in mock_print.call_args_list]
        output = " ".join(calls)
        assert "已加载" in output or "test_plugin" in output


class TestCmdPlugin:
    """测试 cmd_plugin 入口函数"""

    @patch("dochris.cli.cli_plugin._print_plugin_help")
    def test_cmd_plugin_no_command(self, mock_help, reset_pm):
        """测试没有子命令时显示帮助"""
        args = argparse.Namespace(plugin_command=None)

        result = cmd_plugin(args)

        assert result == 0
        mock_help.assert_called_once()

    @patch("dochris.cli.cli_plugin._plugin_list")
    def test_cmd_plugin_list(self, mock_list, reset_pm):
        """测试 list 子命令"""
        args = argparse.Namespace(plugin_command="list")
        mock_list.return_value = 0

        result = cmd_plugin(args)

        assert result == 0
        mock_list.assert_called_once_with(args)

    @patch("dochris.cli.cli_plugin._plugin_info")
    def test_cmd_plugin_info(self, mock_info, reset_pm):
        """测试 info 子命令"""
        args = argparse.Namespace(plugin_command="info", name="test")
        mock_info.return_value = 0

        result = cmd_plugin(args)

        assert result == 0
        mock_info.assert_called_once_with(args)


class TestSetupPluginParser:
    """测试 setup_plugin_parser 函数"""

    def test_setup_plugin_parser_creates_subparsers(self):
        """测试创建子命令解析器"""
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        setup_plugin_parser(subparsers)

        # 测试 list 子命令能正常解析
        args = parser.parse_args(["plugin", "list"])
        assert args.command == "plugin"
        assert args.plugin_command == "list"

        # 测试 info 子命令能正常解析
        args = parser.parse_args(["plugin", "info", "test"])
        assert args.command == "plugin"
        assert args.plugin_command == "info"
        assert args.name == "test"
