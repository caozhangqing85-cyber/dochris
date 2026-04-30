"""插件注册中心

提供轻量级插件管理功能：
- 装饰器注册（@hookimpl）
- 目录扫描加载
- entry_points 加载
- 启用/禁用控制
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from dochris.plugin.loader import discover_hookimpls, load_plugin_module

logger = logging.getLogger(__name__)


class PluginManager:
    """轻量级插件管理器

    支持：
    - 装饰器注册（@hookimpl）
    - 目录扫描加载
    - entry_points 加载（pip install dochris-plugin-xxx）
    - 启用/禁用控制

    Attributes:
        _hooks: {hook_name: [(plugin_name, impl_func)]}
        _plugins: {plugin_name: {"enabled": bool, "module": module}}
        _plugin_order: 插件注册顺序
    """

    def __init__(self) -> None:
        self._hooks: dict[str, list[tuple[str, Any]]] = {}
        self._plugins: dict[str, dict[str, Any]] = {}
        self._plugin_order: list[str] = []

    def register(
        self,
        plugin_name: str,
        hook_name: str,
        impl_func: Callable,
    ) -> None:
        """注册 hook 实现

        Args:
            plugin_name: 插件名称
            hook_name: Hook 名称
            impl_func: 实现函数
        """
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []
        self._hooks[hook_name].append((plugin_name, impl_func))
        logger.debug(f"Registered {plugin_name}.{hook_name}")

    def get_hookimpls(self, hook_name: str) -> list[tuple[str, Any]]:
        """获取某 hook 的所有实现（按注册顺序）

        Args:
            hook_name: Hook 名称

        Returns:
            [(plugin_name, impl_func), ...] 仅包含已启用的插件
        """
        impls = self._hooks.get(hook_name, [])
        return [
            (name, func)
            for name, func in impls
            if self._plugins.get(name, {}).get("enabled", True)
        ]

    def call_hook(
        self,
        hook_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> list[Any]:
        """调用 hook，返回所有实现的返回值列表

        Args:
            hook_name: Hook 名称
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            所有实现的返回值列表
        """
        results: list[Any] = []
        for plugin_name, impl_func in self.get_hookimpls(hook_name):
            try:
                result = impl_func(*args, **kwargs)
                results.append(result)
            except Exception as e:
                logger.warning(
                    f"Hook {hook_name} in {plugin_name} failed: {e}",
                    exc_info=True,
                )
        return results

    def call_hook_firstresult(
        self,
        hook_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """调用 hook，返回第一个非 None 结果

        Args:
            hook_name: Hook 名称
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            第一个非 None 结果，无结果返回 None
        """
        for plugin_name, impl_func in self.get_hookimpls(hook_name):
            try:
                result = impl_func(*args, **kwargs)
                if result is not None:
                    return result
            except Exception as e:
                logger.warning(
                    f"Hook {hook_name} in {plugin_name} failed: {e}",
                    exc_info=True,
                )
        return None

    def load_from_directory(self, plugin_dir: Path) -> list[str]:
        """从目录加载 .py 插件文件

        扫描目录中所有 .py 文件，import 后自动发现 @hookimpl 标记的函数。

        Args:
            plugin_dir: 插件目录路径

        Returns:
            加载的插件名列表
        """
        loaded: list[str] = []
        if not plugin_dir.exists():
            logger.debug(f"Plugin directory not found: {plugin_dir}")
            return loaded

        for py_file in plugin_dir.glob("*.py"):
            # 跳过 __init__.py 和 _ 开头的文件
            if py_file.name.startswith("_") or py_file.name == "__init__.py":
                continue

            module_name = f"plugin_{py_file.stem}"
            try:
                module = load_plugin_module(py_file, module_name)
                hookimpls = discover_hookimpls(module)
                if hookimpls:
                    plugin_name = py_file.stem
                    self._register_module(plugin_name, module, hookimpls)
                    loaded.append(plugin_name)
                    logger.info(f"Loaded plugin: {plugin_name} from {py_file.name}")
            except Exception as e:
                logger.error(f"Failed to load {py_file}: {e}", exc_info=True)

        return loaded

    def load_from_entrypoints(self, group: str = "dochris.plugins") -> list[str]:
        """从 setuptools entry_points 加载插件

        插件包在 pyproject.toml 中声明：
        [project.entry-points."dochris.plugins"]
        my_plugin = "my_plugin_module:setup"

        Args:
            group: Entry point 组名

        Returns:
            加载的插件名列表
        """
        loaded: list[str] = []
        try:
            try:
                # Python 3.10+
                from importlib.metadata import entry_points
            except ImportError:
                from importlib_metadata import entry_points  # type: ignore[no-redef]

            eps = entry_points(group=group)
            for ep in eps:
                try:
                    setup_func = ep.load()
                    if callable(setup_func):
                        setup_func(self)
                        loaded.append(ep.name)
                        logger.info(f"Loaded entry point plugin: {ep.name}")
                except Exception as e:
                    logger.error(
                        f"Failed to load entry point {ep.name}: {e}",
                        exc_info=True,
                    )
        except Exception as e:
            logger.debug(f"Entry points loading failed: {e}")

        return loaded

    def _register_module(
        self,
        plugin_name: str,
        module: Any,
        hookimpls: list[tuple[str, Any]],
    ) -> None:
        """注册模块中的所有 hookimpl

        Args:
            plugin_name: 插件名称
            module: 模块对象
            hookimpls: [(hook_name, func), ...]
        """
        if plugin_name not in self._plugins:
            self._plugins[plugin_name] = {"enabled": True, "module": module}
            self._plugin_order.append(plugin_name)

        for hook_name, func in hookimpls:
            self.register(plugin_name, hook_name, func)

    def enable_plugin(self, name: str) -> None:
        """启用插件

        Args:
            name: 插件名称
        """
        if name in self._plugins:
            self._plugins[name]["enabled"] = True
            logger.info(f"Enabled plugin: {name}")

    def disable_plugin(self, name: str) -> None:
        """禁用插件

        Args:
            name: 插件名称
        """
        if name in self._plugins:
            self._plugins[name]["enabled"] = False
            logger.info(f"Disabled plugin: {name}")

    def is_enabled(self, name: str) -> bool:
        """检查插件是否启用

        Args:
            name: 插件名称

        Returns:
            是否启用
        """
        return self._plugins.get(name, {}).get("enabled", True)

    def list_plugins(self) -> list[dict[str, Any]]:
        """列出所有插件

        Returns:
            插件信息列表
        """
        result: list[dict[str, Any]] = []
        for name in self._plugin_order:
            info = self._plugins.get(name, {})
            hooks = [
                hook_name
                for hook_name in self._hooks
                if any(n == name for n, _ in self._hooks[hook_name])
            ]
            result.append(
                {
                    "name": name,
                    "enabled": info.get("enabled", True),
                    "hooks": hooks,
                }
            )
        return result

    def unregister_plugin(self, name: str) -> None:
        """注销插件

        Args:
            name: 插件名称
        """
        if name in self._plugins:
            del self._plugins[name]
            self._plugin_order = [n for n in self._plugin_order if n != name]
            # 移除相关的 hook 注册
            for hook_name in list(self._hooks.keys()):
                self._hooks[hook_name] = [
                    (n, f) for n, f in self._hooks[hook_name] if n != name
                ]
            logger.info(f"Unregistered plugin: {name}")


# ============================================================
# 全局单例
# ============================================================

_plugin_manager: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    """获取全局 PluginManager 实例

    Returns:
        PluginManager 单例
    """
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager


def reset_plugin_manager() -> None:
    """重置全局 PluginManager（主要用于测试）"""
    global _plugin_manager
    _plugin_manager = None
