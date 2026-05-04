"""测试 plugin/loader 模块"""

import sys
import tempfile
from pathlib import Path

import pytest

from dochris.plugin.hookspec import hookimpl
from dochris.plugin.loader import (
    discover_hookimpls,
    load_plugin_from_code,
    load_plugin_module,
)


class TestDiscoverHookimpls:
    def test_finds_hookimpl_functions(self):
        import types

        mod = types.ModuleType("test_mod")

        @hookimpl
        def ingest_parser(file_path: str):
            return "parsed"

        mod.ingest_parser = ingest_parser
        result = discover_hookimpls(mod)
        assert len(result) == 1
        assert result[0][0] == "ingest_parser"

    def test_ignores_non_hookimpl(self):
        import types

        mod = types.ModuleType("test_mod2")

        def normal_func():
            pass

        mod.normal_func = normal_func
        result = discover_hookimpls(mod)
        assert len(result) == 0

    def test_multiple_hookimpls(self):
        import types

        mod = types.ModuleType("test_mod3")

        @hookimpl
        def ingest_parser(file_path: str):
            return None

        @hookimpl
        def pre_query(query: str):
            return query

        mod.ingest_parser = ingest_parser
        mod.pre_query = pre_query
        result = discover_hookimpls(mod)
        assert len(result) == 2
        names = [r[0] for r in result]
        assert "ingest_parser" in names
        assert "pre_query" in names


class TestLoadPluginModule:
    def test_load_valid_module(self):
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write("X = 42\ndef hello(): return 'world'\n")
            f.flush()
            mod = load_plugin_module(Path(f.name), "test_plugin_valid")
        import os

        os.unlink(f.name)
        assert mod.X == 42
        assert mod.hello() == "world"
        # 清理
        if "test_plugin_valid" in sys.modules:
            del sys.modules["test_plugin_valid"]

    def test_load_syntax_error(self):
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write("def broken(\n")
            f.flush()
            with pytest.raises(SyntaxError):
                load_plugin_module(Path(f.name), "test_plugin_syntax")
        import os

        os.unlink(f.name)

    def test_load_nonexistent_file(self):
        with pytest.raises((ImportError, FileNotFoundError, OSError)):
            load_plugin_module(Path("/nonexistent/plugin.py"), "test_plugin_404")


class TestLoadPluginFromCode:
    def test_load_valid_code(self):
        code = "Y = 99\ndef add(a, b): return a + b\n"
        mod = load_plugin_from_code(code, "test_code_plugin")
        assert mod.Y == 99
        assert mod.add(1, 2) == 3
        if "test_code_plugin" in sys.modules:
            del sys.modules["test_code_plugin"]

    def test_load_invalid_code(self):
        code = "raise ValueError('bad')"
        with pytest.raises(ValueError):
            load_plugin_from_code(code, "test_bad_plugin")

    def test_cleanup_on_failure(self):
        code = "raise RuntimeError('fail')"
        with pytest.raises(RuntimeError):
            load_plugin_from_code(code, "test_cleanup_plugin")
        assert "test_cleanup_plugin" not in sys.modules
