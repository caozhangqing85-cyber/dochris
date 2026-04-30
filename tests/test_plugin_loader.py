"""
测试插件加载器 (loader.py)
"""

from unittest.mock import MagicMock, patch

import pytest

from dochris.plugin import PluginManager, reset_plugin_manager
from dochris.plugin.loader import discover_hookimpls, load_plugin_from_code, load_plugin_module


@pytest.fixture
def clean_pm():
    """提供干净的 PluginManager 实例"""
    reset_plugin_manager()
    pm = PluginManager()
    return pm


class TestDiscoverHookimpls:
    """测试 discover_hookimpls 函数"""

    def test_discover_hookimpls_finds_marked_functions(self):
        """测试发现带 @hookimpl 标记的函数"""
        # 带标记的函数
        def hook1():
            pass

        hook1._is_hookimpl = True

        def hook2():
            pass

        hook2._is_hookimpl = True

        # 不带标记的函数
        def regular_func():
            pass

        # 创建真实的模块对象
        import types

        mock_module = types.ModuleType("test_module")
        mock_module.hook1 = hook1
        mock_module.hook2 = hook2
        mock_module.regular_func = regular_func

        with patch("dochris.plugin.loader.inspect.getmembers") as mock_getmembers:
            mock_getmembers.return_value = [
                ("hook1", hook1),
                ("hook2", hook2),
                ("regular_func", regular_func),
            ]

            hookimpls = discover_hookimpls(mock_module)

            assert len(hookimpls) == 2
            assert ("hook1", hook1) in hookimpls
            assert ("hook2", hook2) in hookimpls

    def test_discover_hookimpls_returns_empty_when_no_hooks(self):
        """测试没有 hookimpl 时返回空列表"""
        mock_module = MagicMock()
        mock_module.__name__ = "test_module"

        with patch("dochris.plugin.loader.inspect.getmembers") as mock_getmembers:
            # 返回没有标记的函数
            mock_getmembers.return_value = [("func1", lambda: None)]

            hookimpls = discover_hookimpls(mock_module)

            assert hookimpls == []


class TestLoadPluginModule:
    """测试 load_plugin_module 函数"""

    def test_load_plugin_module_from_file(self, tmp_path):
        """测试从文件加载插件模块"""
        # 创建测试插件文件
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

        # 加载模块
        module = load_plugin_module(plugin_file, "test_plugin_module")

        # 验证模块已加载
        assert module is not None
        assert hasattr(module, "test_hook")
        assert module.test_hook() == "test"

        # 清理 sys.modules
        import sys

        if "test_plugin_module" in sys.modules:
            del sys.modules["test_plugin_module"]

    def test_load_plugin_module_with_syntax_error(self, tmp_path):
        """测试加载语法错误的插件"""
        plugin_file = tmp_path / "bad_plugin.py"
        plugin_file.write_text("def broken(:\n    pass", encoding="utf-8")

        with pytest.raises(SyntaxError):
            load_plugin_module(plugin_file, "bad_plugin")

    def test_load_plugin_module_nonexistent_file(self, tmp_path):
        """测试加载不存在的文件"""
        # 创建一个空的模块来模拟不存在的文件
        # 由于 load_plugin_module 使用 importlib，不存在的文件会导致 OSError
        nonexistent = tmp_path / "nonexistent.py"

        with pytest.raises((ImportError, OSError)):
            load_plugin_module(nonexistent, "nonexistent")


class TestLoadPluginFromCode:
    """测试 load_plugin_from_code 函数"""

    def test_load_plugin_from_code_string(self):
        """测试从代码字符串加载插件"""
        code = """
def my_hook():
    return "hook_result"

my_hook._is_hookimpl = True
"""

        module = load_plugin_from_code(code, "code_plugin")

        assert hasattr(module, "my_hook")
        assert module.my_hook() == "hook_result"

        # 清理
        import sys

        if "code_plugin" in sys.modules:
            del sys.modules["code_plugin"]

    def test_load_plugin_from_code_with_syntax_error(self):
        """测试从有语法错误的代码加载"""
        code = "def broken(:\n    pass"

        with pytest.raises(Exception):
            load_plugin_from_code(code, "broken_plugin")


class TestLoadFromDirectory:
    """测试 PluginManager.load_from_directory 方法"""

    def test_load_plugin_from_directory(self, clean_pm, tmp_path):
        """测试从目录加载 .py 插件"""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        # 创建测试插件
        (plugin_dir / "plugin1.py").write_text(
            """
def hook_a():
    return "a"

hook_a._is_hookimpl = True
""",
            encoding="utf-8",
        )

        (plugin_dir / "plugin2.py").write_text(
            """
def hook_b():
    return "b"

hook_b._is_hookimpl = True
""",
            encoding="utf-8",
        )

        # 跳过的文件
        (plugin_dir / "_internal.py").write_text("# internal")
        (plugin_dir / "__init__.py").write_text("# init")

        # 加载插件
        loaded = clean_pm.load_from_directory(plugin_dir)

        # 验证
        assert len(loaded) == 2
        assert "plugin1" in loaded
        assert "plugin2" in loaded
        assert "_internal" not in loaded
        assert "__init__" not in loaded

        # 验证 hook 已注册
        results_a = clean_pm.call_hook("hook_a")
        assert results_a == ["a"]

        results_b = clean_pm.call_hook("hook_b")
        assert results_b == ["b"]

    def test_load_empty_directory(self, clean_pm, tmp_path):
        """测试加载空目录"""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        loaded = clean_pm.load_from_directory(empty_dir)

        assert loaded == []

    def test_load_nonexistent_directory(self, clean_pm, tmp_path):
        """测试加载不存在的目录"""
        nonexistent = tmp_path / "nonexistent"

        loaded = clean_pm.load_from_directory(nonexistent)

        assert loaded == []

    def test_load_plugin_with_exception(self, clean_pm, tmp_path):
        """测试加载有异常的插件不崩溃"""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        # 正常插件
        (plugin_dir / "good.py").write_text(
            """
def good_hook():
    return "good"

good_hook._is_hookimpl = True
""",
            encoding="utf-8",
        )

        # 有语法错误的插件
        (plugin_dir / "bad.py").write_text("def broken(:\n    pass", encoding="utf-8")

        # 加载应该成功（bad 插件被跳过）
        loaded = clean_pm.load_from_directory(plugin_dir)

        assert "good" in loaded
        assert "bad" not in loaded

        # good 插件应该仍然工作
        results = clean_pm.call_hook("good_hook")
        assert results == ["good"]

    def test_load_plugin_without_hookimpl(self, clean_pm, tmp_path):
        """测试加载没有 hookimpl 的文件"""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        # 没有 hookimpl 的文件
        (plugin_dir / "no_hook.py").write_text(
            """
def regular_function():
    return "no hook marker"
""",
            encoding="utf-8",
        )

        loaded = clean_pm.load_from_directory(plugin_dir)

        # 文件被扫描但不注册（没有 hookimpl）
        assert loaded == []


class TestLoadFromEntrypoints:
    """测试 load_from_entrypoints 方法"""

    def test_load_from_entrypoints_no_importlib_metadata(self, clean_pm):
        """测试没有 importlib.metadata 时的情况"""
        # 模拟 importlib.metadata 不可用
        with patch("builtins.__import__") as mock_import:
            # 第一次调用导入 importlib.metadata 时抛出 ImportError
            # 第二次调用导入 importlib_metadata 也抛出 ImportError
            mock_import.side_effect = [ImportError, ImportError]

            loaded = clean_pm.load_from_entrypoints()
            # 应该返回空列表而不是崩溃
            assert loaded == []

    def test_load_from_entrypoints_with_mock(self, clean_pm):
        """测试模拟 entry_points 加载"""
        # 创建 mock entry point
        mock_ep = MagicMock()
        mock_ep.name = "test_plugin"

        mock_setup = MagicMock()
        mock_ep.load.return_value = mock_setup

        # 模拟 entry_points 函数返回包含 mock_ep 的可迭代对象
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([mock_ep]))

        with patch("importlib.metadata.entry_points", return_value=mock_result):
            loaded = clean_pm.load_from_entrypoints()

            # 应该调用 setup 函数
            mock_setup.assert_called_once_with(clean_pm)
            assert "test_plugin" in loaded
