"""覆盖率提升 v8 — cli_plugin 异常分支 + _load_plugins_from_settings + 其他小模块"""

from unittest.mock import MagicMock, patch


# ============================================================
# cli_plugin.py — 异常分支 + _load_plugins_from_settings
# ============================================================
class TestCliPluginExceptions:
    def test_plugin_load_syntax_error(self, tmp_path):
        """加载有语法错误的插件文件"""
        from dochris.cli.cli_plugin import _plugin_load

        args = MagicMock(path=str(tmp_path / "bad.py"))
        # 创建一个有语法错误的 .py 文件
        (tmp_path / "bad.py").write_text("def foo(\n", encoding="utf-8")
        with patch("dochris.plugin.registry.get_plugin_manager") as mock_pm:
            mock_pm.return_value.load_plugin_from_file.side_effect = SyntaxError("bad syntax")
            assert _plugin_load(args) == 1

    def test_plugin_load_import_error(self, tmp_path):
        from dochris.cli.cli_plugin import _plugin_load

        args = MagicMock(path=str(tmp_path / "bad2.py"))
        (tmp_path / "bad2.py").write_text("import nonexistent_module_xyz\n", encoding="utf-8")
        with patch("dochris.plugin.registry.get_plugin_manager") as mock_pm:
            mock_pm.return_value.load_plugin_from_file.side_effect = ImportError("no module")
            assert _plugin_load(args) == 1

    def test_plugin_load_unexpected_error(self, tmp_path):
        from dochris.cli.cli_plugin import _plugin_load

        args = MagicMock(path=str(tmp_path / "bad3.py"))
        (tmp_path / "bad3.py").write_text("pass\n", encoding="utf-8")
        with patch("dochris.plugin.registry.get_plugin_manager") as mock_pm:
            mock_pm.return_value.load_plugin_from_file.side_effect = RuntimeError("unexpected")
            assert _plugin_load(args) == 1


class TestCliPluginLoadFromSettings:
    def test_load_plugins_from_settings(self):
        from dochris.cli.cli_plugin import _load_plugins_from_settings

        mock_settings = MagicMock()
        mock_settings.plugin_dirs = []
        mock_settings.plugins_enabled = []
        mock_settings.plugins_disabled = []
        mock_pm = MagicMock()
        mock_pm.load_from_directory.return_value = []
        with (
            patch("dochris.cli.cli_plugin.get_settings", return_value=mock_settings),
            patch("dochris.cli.cli_plugin.get_plugin_manager", return_value=mock_pm),
        ):
            result = _load_plugins_from_settings()
            assert result == 0

    def test_load_plugins_with_dirs(self, tmp_path):
        from dochris.cli.cli_plugin import _load_plugins_from_settings

        mock_settings = MagicMock()
        mock_settings.plugin_dirs = [str(tmp_path / "plugins")]
        mock_settings.plugins_enabled = ["test_plugin"]
        mock_settings.plugins_disabled = ["disabled_plugin"]
        mock_pm = MagicMock()
        mock_pm.load_from_directory.return_value = []
        with (
            patch("dochris.cli.cli_plugin.get_settings", return_value=mock_settings),
            patch("dochris.cli.cli_plugin.get_plugin_manager", return_value=mock_pm),
        ):
            _load_plugins_from_settings()
            mock_pm.enable_plugin.assert_called_with("test_plugin")
            mock_pm.disable_plugin.assert_called_with("disabled_plugin")


# plugin info hookspec 测试依赖内部结构，跳过


# ============================================================
# core/utils.py — 未覆盖的边界分支 (lines 268-269)
# ============================================================
class TestCoreUtils:
    def test_safe_read_text_not_exists(self, tmp_path):
        from dochris.core.utils import safe_read_text

        result = safe_read_text(tmp_path / "nonexistent.txt")
        assert result is None

    def test_safe_read_text_success(self, tmp_path):
        from dochris.core.utils import safe_read_text

        f = tmp_path / "test.txt"
        f.write_text("hello world", encoding="utf-8")
        result = safe_read_text(f)
        assert result == "hello world"


# ============================================================
# manifest.py — line 222
# ============================================================
class TestManifestBranches:
    def test_get_all_manifests_empty(self, tmp_path):
        from dochris.manifest import get_all_manifests

        result = get_all_manifests(tmp_path)
        assert result == []

    def test_get_all_manifests_by_status(self, tmp_path):
        from dochris.manifest import get_all_manifests

        result = get_all_manifests(tmp_path, status="compiled")
        assert result == []
