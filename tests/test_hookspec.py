"""测试 plugin/hookspec 模块"""

import pytest

from dochris.plugin.hookspec import (
    HookSpec,
    get_hookspec,
    hookimpl,
    hookspec,
    list_hookspecs,
)


class TestHookSpec:
    def test_init_defaults(self):
        spec = HookSpec("test_hook")
        assert spec.name == "test_hook"
        assert spec.firstresult is False
        assert spec.historic is False

    def test_init_custom(self):
        spec = HookSpec("my_hook", firstresult=True, historic=True)
        assert spec.firstresult is True
        assert spec.historic is True

    def test_repr(self):
        spec = HookSpec("my_hook", firstresult=True)
        r = repr(spec)
        assert "my_hook" in r
        assert "firstresult=True" in r

    def test_slots(self):
        spec = HookSpec("x")
        assert hasattr(spec, "__slots__")
        with pytest.raises(AttributeError):
            spec.nonexistent = "fail"


class TestHookspecDecorator:
    def test_marks_function(self):
        @hookspec
        def my_test_hook():
            pass

        assert getattr(my_test_hook, "_is_hookspec", False) is True

    def test_registers_in_global(self):
        @hookspec
        def unique_test_hook_xyz():
            pass

        spec = get_hookspec("unique_test_hook_xyz")
        assert spec is not None
        assert isinstance(spec, HookSpec)
        assert spec.name == "unique_test_hook_xyz"


class TestHookimplDecorator:
    def test_marks_function(self):
        @hookimpl
        def my_impl():
            pass

        assert getattr(my_impl, "_is_hookimpl", False) is True

    def test_preserves_function(self):
        @hookimpl
        def my_impl(x):
            return x * 2

        assert my_impl(5) == 10


class TestGetHookspec:
    def test_returns_none_for_unknown(self):
        assert get_hookspec("nonexistent_hook_xyz") is None

    def test_returns_existing(self):
        # 6 个内置 hookspec 应该已注册
        spec = get_hookspec("ingest_parser")
        assert spec is not None
        assert spec.name == "ingest_parser"


class TestListHookspecs:
    def test_includes_builtin_hooks(self):
        names = list_hookspecs()
        assert "ingest_parser" in names
        assert "pre_compile" in names
        assert "post_compile" in names
        assert "quality_score" in names
        assert "pre_query" in names
        assert "post_query" in names


class TestBuiltinHookspecs:
    """测试 6 个内置扩展点是否正确定义"""

    def test_ingest_parser_registered(self):
        spec = get_hookspec("ingest_parser")
        assert spec is not None

    def test_pre_compile_registered(self):
        spec = get_hookspec("pre_compile")
        assert spec is not None

    def test_post_compile_registered(self):
        spec = get_hookspec("post_compile")
        assert spec is not None

    def test_quality_score_registered(self):
        spec = get_hookspec("quality_score")
        assert spec is not None

    def test_pre_query_registered(self):
        spec = get_hookspec("pre_query")
        assert spec is not None

    def test_post_query_registered(self):
        spec = get_hookspec("post_query")
        assert spec is not None

    def test_total_count(self):
        names = list_hookspecs()
        assert len(names) >= 6
