"""Dochris 插件系统

轻量级插件框架，支持通过 Hook 扩展系统功能。

基本用法:
    from dochris.plugin import PluginManager, hookimpl

    # 定义插件
    @hookimpl
    def pre_compile(text: str, metadata: dict) -> tuple[str, dict]:
        clean_text = text.strip()
        return clean_text, metadata

    # 注册插件
    pm = PluginManager()
    pm.load_from_directory(Path("/path/to/plugins"))

    # 调用 hook
    results = pm.call_hook("pre_compile", text, metadata)
"""

from __future__ import annotations

from dochris.plugin.hookspec import (
    get_hookspec,
    hookimpl,
    hookspec,
    list_hookspecs,
)
from dochris.plugin.registry import (
    PluginManager,
    get_plugin_manager,
    reset_plugin_manager,
)

__all__ = [
    # 核心类
    "PluginManager",
    # 装饰器
    "hookimpl",
    "hookspec",
    # 工厂函数
    "get_plugin_manager",
    "reset_plugin_manager",
    "get_hookspec",
    "list_hookspecs",
]
