"""测试 plugin/loader.py 和 plugin/hookspec.py 模块"""

import sys
import types
from pathlib import Path

import pytest


class TestDiscoverHookimpls:
    """测试 discover_hookimpls"""

    def test_finds_hookimpl_functions(self):
        from dochris.plugin.loader import discover_hookimpls

        module = types.ModuleType("test_plugin")

        def regular_func():
            pass

        def hook_func():
            pass

        hook_func._is_hookimpl = True  # type: ignore[attr-defined]

        module.regular_func = regular_func
        module.hook_func = hook_func

        result = discover_hookimpls(module)
        assert len(result) == 1
        assert result[0][0] == "hook_func"
        assert result[0][1] is hook_func

    def test_empty_module(self):
        from dochris.plugin.loader import discover_hookimpls

        module = types.ModuleType("empty")
        result = discover_hookimpls(module)
        assert result == []

    def test_multiple_hookimpls(self):
        from dochris.plugin.loader import discover_hookimpls

        module = types.ModuleType("multi")

        def func_a():
            pass

        func_a._is_hookimpl = True

        def func_b():
            pass

        func_b._is_hookimpl = True

        module.func_a = func_a
        module.func_b = func_b

        result = discover_hookimpls(module)
        assert len(result) == 2
        names = {r[0] for r in result}
        assert names == {"func_a", "func_b"}


class TestLoadPluginModule:
    """测试 load_plugin_module"""

    def test_load_valid_python_file(self, tmp_path):
        from dochris.plugin.loader import load_plugin_module

        py_file = tmp_path / "my_plugin.py"
        py_file.write_text("VALUE = 42\n")

        module = load_plugin_module(py_file, "test_load_valid")
        assert module.VALUE == 42

    def test_load_nonexistent_file_raises(self):
        from dochris.plugin.loader import load_plugin_module

        with pytest.raises(Exception):
            load_plugin_module(Path("/nonexistent/file.py"), "test_bad")

    def test_load_syntax_error_cleans_up(self, tmp_path):
        from dochris.plugin.loader import load_plugin_module

        py_file = tmp_path / "bad_syntax.py"
        py_file.write_text("def broken(\n")

        mod_name = "test_syntax_error_cleanup"
        with pytest.raises(SyntaxError):
            load_plugin_module(py_file, mod_name)

        assert mod_name not in sys.modules


class TestLoadPluginFromCode:
    """测试 load_plugin_from_code"""

    def test_load_valid_code(self):
        from dochris.plugin.loader import load_plugin_from_code

        module = load_plugin_from_code("X = 99", "test_code_valid")
        assert module.X == 99

    def test_load_invalid_code_raises(self):
        from dochris.plugin.loader import load_plugin_from_code

        mod_name = "test_code_invalid"
        with pytest.raises(Exception):
            load_plugin_from_code("raise ValueError('bad')", mod_name)
        assert mod_name not in sys.modules

    def test_loaded_module_in_sys_modules(self):
        from dochris.plugin.loader import load_plugin_from_code

        mod_name = "test_sys_modules_check"
        module = load_plugin_from_code("PASS = True", mod_name)
        assert sys.modules[mod_name] is module


class TestHookSpec:
    """测试 HookSpec 类"""

    def test_init_defaults(self):
        from dochris.plugin.hookspec import HookSpec

        spec = HookSpec("test_hook")
        assert spec.name == "test_hook"
        assert spec.firstresult is False
        assert spec.historic is False

    def test_init_custom(self):
        from dochris.plugin.hookspec import HookSpec

        spec = HookSpec("hook2", firstresult=True, historic=True)
        assert spec.firstresult is True
        assert spec.historic is True

    def test_repr(self):
        from dochris.plugin.hookspec import HookSpec

        spec = HookSpec("my_hook", firstresult=True)
        r = repr(spec)
        assert "my_hook" in r
        assert "firstresult=True" in r


class TestHookspecDecorator:
    """测试 hookspec 装饰器"""

    def test_hookspec_adds_marker(self):
        from dochris.plugin.hookspec import hookspec

        @hookspec
        def my_test_hook(x: int) -> int: ...

        assert getattr(my_test_hook, "_is_hookspec", False) is True

    def test_hookspec_registers_in_global(self):
        from dochris.plugin.hookspec import get_hookspec, hookspec

        @hookspec
        def unique_test_hook_xyz(): ...

        spec = get_hookspec("unique_test_hook_xyz")
        assert spec is not None
        assert spec.name == "unique_test_hook_xyz"


class TestHookimplDecorator:
    """测试 hookimpl 装饰器"""

    def test_hookimpl_adds_marker(self):
        from dochris.plugin.hookspec import hookimpl

        @hookimpl
        def my_impl():
            return "ok"

        assert getattr(my_impl, "_is_hookimpl", False) is True
        assert my_impl() == "ok"


class TestGetHookspec:
    """测试 get_hookspec"""

    def test_get_existing(self):
        from dochris.plugin.hookspec import get_hookspec

        # 这些是模块级别注册的 hooks
        spec = get_hookspec("ingest_parser")
        assert spec is not None
        assert spec.name == "ingest_parser"

    def test_get_nonexistent(self):
        from dochris.plugin.hookspec import get_hookspec

        assert get_hookspec("nonexistent_hook_12345") is None


class TestListHookspecs:
    """测试 list_hookspecs"""

    def test_list_returns_known_hooks(self):
        from dochris.plugin.hookspec import list_hookspecs

        specs = list_hookspecs()
        assert "ingest_parser" in specs
        assert "pre_compile" in specs
        assert "post_compile" in specs
        assert "quality_score" in specs
        assert "pre_query" in specs
        assert "post_query" in specs

    def test_list_returns_list_type(self):
        from dochris.plugin.hookspec import list_hookspecs

        result = list_hookspecs()
        assert isinstance(result, list)
        assert len(result) >= 6
