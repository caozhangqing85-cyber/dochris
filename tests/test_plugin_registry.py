"""
测试 PluginManager 插件注册中心
"""

import pytest

from dochris.plugin import PluginManager, get_plugin_manager, reset_plugin_manager


@pytest.fixture
def clean_pm():
    """提供干净的 PluginManager 实例"""
    reset_plugin_manager()
    pm = PluginManager()
    return pm


@pytest.fixture
def sample_hookimpl():
    """示例 hookimpl 函数"""

    def sample_hook(arg: str) -> str:
        return f"processed: {arg}"

    # 模拟 hookimpl 标记
    sample_hook._is_hookimpl = True
    return sample_hook


class TestPluginManager:
    """测试 PluginManager 类"""

    def test_register_and_call_hook(self, clean_pm, sample_hookimpl):
        """测试注册并调用 hook"""
        # 注册 hook
        clean_pm.register("test_plugin", "sample_hook", sample_hookimpl)

        # 调用 hook
        results = clean_pm.call_hook("sample_hook", "test")

        assert len(results) == 1
        assert results[0] == "processed: test"

    def test_call_hook_firstresult(self, clean_pm):
        """测试 firstresult 模式取第一个非 None 结果"""

        def hook1(x: int) -> int | None:
            return None

        def hook2(x: int) -> int | None:
            return x * 2

        def hook3(x: int) -> int | None:
            return x * 3

        # 注册多个 hook
        clean_pm.register("p1", "calc", hook1)
        clean_pm.register("p2", "calc", hook2)
        clean_pm.register("p3", "calc", hook3)

        # firstresult 应该返回第一个非 None 结果
        result = clean_pm.call_hook_firstresult("calc", 5)

        assert result == 10  # hook2 的结果

    def test_multiple_plugins_same_hook(self, clean_pm):
        """测试同一 hook 多个插件按顺序调用"""
        call_order = []

        def hook_a():
            call_order.append("a")
            return "A"

        def hook_b():
            call_order.append("b")
            return "B"

        def hook_c():
            call_order.append("c")
            return "C"

        # 按顺序注册
        clean_pm.register("plugin_a", "test", hook_a)
        clean_pm.register("plugin_b", "test", hook_b)
        clean_pm.register("plugin_c", "test", hook_c)

        # 调用 hook
        results = clean_pm.call_hook("test")

        # 验证调用顺序
        assert call_order == ["a", "b", "c"]
        assert results == ["A", "B", "C"]

    def test_enable_disable_plugin(self, clean_pm, sample_hookimpl):
        """测试启用/禁用控制"""

        def hook_func():
            return "enabled"

        clean_pm.register("my_plugin", "test_hook", hook_func)
        clean_pm._plugins["my_plugin"] = {"enabled": True, "module": None}

        # 默认启用
        assert clean_pm.is_enabled("my_plugin") is True
        results = clean_pm.call_hook("test_hook")
        assert results == ["enabled"]

        # 禁用插件
        clean_pm.disable_plugin("my_plugin")
        assert clean_pm.is_enabled("my_plugin") is False
        results = clean_pm.call_hook("test_hook")
        assert results == []

        # 重新启用
        clean_pm.enable_plugin("my_plugin")
        assert clean_pm.is_enabled("my_plugin") is True
        results = clean_pm.call_hook("test_hook")
        assert results == ["enabled"]

    def test_disabled_plugin_not_called(self, clean_pm):
        """测试禁用的插件不参与 hook 调用"""
        call_log = []

        def hook_enabled():
            call_log.append("enabled")
            return "enabled_result"

        def hook_disabled():
            call_log.append("disabled")
            return "disabled_result"

        clean_pm.register("plugin_enabled", "test", hook_enabled)
        clean_pm.register("plugin_disabled", "test", hook_disabled)

        # 设置插件状态
        clean_pm._plugins["plugin_enabled"] = {"enabled": True, "module": None}
        clean_pm._plugins["plugin_disabled"] = {"enabled": False, "module": None}

        # 调用 hook
        results = clean_pm.call_hook("test")

        # 只有启用的插件被调用
        assert call_log == ["enabled"]
        assert results == ["enabled_result"]

    def test_list_plugins(self, clean_pm):
        """测试列出插件信息"""

        def hook1():
            pass

        def hook2():
            pass

        # 使用 _register_module 注册插件（会更新 _plugin_order）
        clean_pm._register_module(
            "plugin_a", None, [("hook_x", hook1), ("hook_y", hook2)]
        )
        clean_pm._register_module("plugin_b", None, [("hook_x", hook1)])

        # 设置启用状态
        clean_pm._plugins["plugin_a"]["enabled"] = True
        clean_pm._plugins["plugin_b"]["enabled"] = False

        # 列出插件
        plugins = clean_pm.list_plugins()

        assert len(plugins) == 2

        # 验证 plugin_a
        plugin_a = next(p for p in plugins if p["name"] == "plugin_a")
        assert plugin_a["enabled"] is True
        assert set(plugin_a["hooks"]) == {"hook_x", "hook_y"}

        # 验证 plugin_b
        plugin_b = next(p for p in plugins if p["name"] == "plugin_b")
        assert plugin_b["enabled"] is False
        assert plugin_b["hooks"] == ["hook_x"]

    def test_unregister_plugin(self, clean_pm):
        """测试取消注册插件"""

        def hook_func():
            return "result"

        # 注册插件
        clean_pm.register("my_plugin", "test_hook", hook_func)
        clean_pm._plugins["my_plugin"] = {"enabled": True, "module": None}

        # 验证已注册
        assert "my_plugin" in clean_pm._plugins
        assert "test_hook" in clean_pm._hooks
        results = clean_pm.call_hook("test_hook")
        assert len(results) == 1

        # 取消注册
        clean_pm.unregister_plugin("my_plugin")

        # 验证已移除
        assert "my_plugin" not in clean_pm._plugins
        assert "my_plugin" not in clean_pm._plugin_order
        results = clean_pm.call_hook("test_hook")
        assert len(results) == 0

    def test_get_hookimpls_returns_only_enabled(self, clean_pm):
        """测试 get_hookimpls 只返回启用的插件"""

        def hook1():
            return "a"

        def hook2():
            return "b"

        def hook3():
            return "c"

        # 使用 _register_module 注册
        clean_pm._register_module("p1", None, [("test", hook1)])
        clean_pm._register_module("p2", None, [("test", hook2)])
        clean_pm._register_module("p3", None, [("test", hook3)])

        # 设置状态：p1 启用，p2 禁用，p3 启用
        clean_pm._plugins["p1"]["enabled"] = True
        clean_pm._plugins["p2"]["enabled"] = False
        clean_pm._plugins["p3"]["enabled"] = True

        # 获取 hookimpls
        impls = clean_pm.get_hookimpls("test")

        # 只返回启用的插件
        assert len(impls) == 2
        assert impls[0][0] == "p1"
        assert impls[1][0] == "p3"


class TestPluginManagerSingleton:
    """测试 PluginManager 单例"""

    def test_get_plugin_manager_singleton(self):
        """测试单例模式"""
        reset_plugin_manager()

        pm1 = get_plugin_manager()
        pm2 = get_plugin_manager()

        # 应该是同一个实例
        assert pm1 is pm2

    def test_reset_plugin_manager(self):
        """测试重置单例"""
        pm1 = get_plugin_manager()

        # 注册一些内容
        pm1.register("test", "hook", lambda: None)

        # 重置
        reset_plugin_manager()

        pm2 = get_plugin_manager()

        # 应该是新实例，之前的内容已清空
        assert pm1 is not pm2
        assert len(pm2._plugins) == 0

    def test_plugin_state_persistence(self):
        """测试单例状态持久化"""
        reset_plugin_manager()

        pm = get_plugin_manager()
        pm.register("test_plugin", "test_hook", lambda: "result")
        pm._plugins["test_plugin"] = {"enabled": True, "module": None}

        # 再次获取单例
        pm2 = get_plugin_manager()

        # 状态应该保留
        assert "test_plugin" in pm2._plugins
        results = pm2.call_hook("test_hook")
        assert results == ["result"]
