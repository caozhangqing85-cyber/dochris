"""补充测试 cli_plugin.py — 覆盖 info 页面 disabled + hooks 分支"""

import argparse
from unittest.mock import MagicMock, patch

import pytest

from dochris.plugin import get_plugin_manager, reset_plugin_manager


@pytest.fixture
def reset_pm():
    reset_plugin_manager()


class TestPluginInfoDetailed:
    """覆盖 _plugin_info 的 disabled + hooks + hookspec 分支"""

    @patch("dochris.cli.cli_plugin.print")
    def test_plugin_info_disabled_with_hooks(self, mock_print, reset_pm):
        """disabled 插件有 hooks，且 hookspec 存在"""
        from dochris.cli.cli_plugin import _plugin_info
        from dochris.plugin import get_plugin_manager

        pm = get_plugin_manager()

        def hook_func():
            pass

        pm._register_module("test_plugin", None, [("test_hook", hook_func)])
        pm._plugins["test_plugin"]["enabled"] = False  # disabled

        mock_spec = MagicMock()
        mock_spec.firstresult = True
        mock_spec.historic = False

        with patch("dochris.plugin.hookspec.get_hookspec", return_value=mock_spec):
            args = argparse.Namespace(name="test_plugin")
            result = _plugin_info(args)

        assert result == 0
        output = " ".join(str(c) for c in mock_print.call_args_list)
        assert "禁用" in output

    @patch("dochris.cli.cli_plugin.print")
    def test_plugin_info_no_hooks(self, mock_print, reset_pm):
        """插件没有 hooks"""
        from dochris.cli.cli_plugin import _plugin_info
        from dochris.plugin import get_plugin_manager

        pm = get_plugin_manager()
        pm._register_module("nohook_plugin", None, [])

        args = argparse.Namespace(name="nohook_plugin")
        result = _plugin_info(args)

        assert result == 0
        output = " ".join(str(c) for c in mock_print.call_args_list)
        assert "无" in output


class TestPluginLoadGenericException:
    """覆盖 _plugin_load 的 generic Exception 分支"""

    @patch("dochris.cli.cli_plugin.print")
    def test_plugin_load_generic_exception(self, mock_print, reset_pm, tmp_path):
        """加载插件时抛出 generic Exception"""
        from dochris.cli.cli_plugin import _plugin_load

        plugin_file = tmp_path / "bad_plugin.py"
        plugin_file.write_text(
            """
def test_hook():
    return "test"
test_hook._is_hookimpl = True
""",
            encoding="utf-8",
        )

        with patch("dochris.cli.cli_plugin.load_plugin_module", side_effect=Exception("generic error")):
            args = argparse.Namespace(path=str(plugin_file))
            result = _plugin_load(args)

        assert result == 1
        output = " ".join(str(c) for c in mock_print.call_args_list)
        assert "加载失败" in output
