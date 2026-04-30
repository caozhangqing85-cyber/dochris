#!/usr/bin/env python3
"""
kb plugin 命令：插件管理

提供插件列表、详情查看、启用/禁用、手动加载等功能。
"""

import argparse
from pathlib import Path

from dochris.cli.cli_utils import dim, error, info, success, warning
from dochris.plugin import get_plugin_manager
from dochris.plugin.loader import discover_hookimpls, load_plugin_module
from dochris.settings import get_settings


def cmd_plugin(args: argparse.Namespace) -> int:
    """插件管理命令入口

    Args:
        args: 命令行参数

    Returns:
        退出码（0 表示成功，非 0 表示错误）
    """
    if not args.plugin_command:
        _print_plugin_help()
        return 0

    if args.plugin_command == "list":
        return _plugin_list(args)
    elif args.plugin_command == "info":
        return _plugin_info(args)
    elif args.plugin_command == "enable":
        return _plugin_enable(args)
    elif args.plugin_command == "disable":
        return _plugin_disable(args)
    elif args.plugin_command == "load":
        return _plugin_load(args)
    else:
        print(error(f"未知命令: {args.plugin_command}"))
        return 1


def _print_plugin_help() -> None:
    """打印插件命令帮助"""
    print("\n" + "=" * 60)
    print(info("插件管理命令"))
    print("=" * 60 + "\n")
    print("子命令:")
    print("  list              列出所有已注册插件")
    print("  info <name>       查看插件详情")
    print("  enable <name>     启用插件")
    print("  disable <name>    禁用插件")
    print("  load <path>       手动加载插件文件\n")
    print("示例:")
    print("  kb plugin list")
    print("  kb plugin info epub_parser")
    print("  kb plugin enable compile_notify")
    print("  kb plugin disable query_enhance")
    print("  kb plugin load /path/to/my_plugin.py\n")


def _plugin_list(args: argparse.Namespace) -> int:
    """列出所有已注册插件

    Args:
        args: 命令行参数

    Returns:
        退出码
    """
    pm = get_plugin_manager()
    plugins = pm.list_plugins()

    if not plugins:
        print(warning("没有已注册的插件"))
        print(dim("提示: 将插件文件放入插件目录，或使用 'kb plugin load <path>' 加载"))
        return 0

    print("\n" + "=" * 60)
    print(info("已注册插件"))
    print("=" * 60 + "\n")

    enabled_count = 0
    for plugin in plugins:
        name = plugin["name"]
        enabled = plugin["enabled"]
        hooks = plugin.get("hooks", [])

        if enabled:
            enabled_count += 1
            status_icon = success("🟢")
            status_text = "启用"
        else:
            status_icon = warning("🔴")
            status_text = "禁用"

        # 格式化 hooks 列表
        hooks_str = ", ".join(hooks) if hooks else dim("无")

        print(f"{status_icon} {info(name):<20} hooks: {hooks_str:<40} 状态: {status_text}")

    print(f"\n已注册 {len(plugins)} 个插件，{enabled_count} 个启用\n")
    return 0


def _plugin_info(args: argparse.Namespace) -> int:
    """查看插件详情

    Args:
        args: 命令行参数（args.name 为插件名）

    Returns:
        退出码
    """
    if not args.name:
        print(error("缺少插件名称"))
        print(dim("用法: kb plugin info <name>"))
        return 1

    pm = get_plugin_manager()
    plugins = pm.list_plugins()

    plugin = None
    for p in plugins:
        if p["name"] == args.name:
            plugin = p
            break

    if not plugin:
        print(error(f"插件不存在: {args.name}"))
        print(dim("使用 'kb plugin list' 查看所有插件"))
        return 1

    print("\n" + "=" * 60)
    print(info(f"插件详情: {plugin['name']}"))
    print("=" * 60 + "\n")

    enabled = plugin["enabled"]
    if enabled:
        print(f"状态: {success('启用')}")
    else:
        print(f"状态: {warning('禁用')}")

    hooks = plugin.get("hooks", [])
    if hooks:
        print(f"\n注册的 Hook ({len(hooks)} 个):")
        for hook in hooks:
            print(f"  • {info(hook)}")
    else:
        print("\n注册的 Hook: 无")

    # 获取 HookSpec 详情
    from dochris.plugin.hookspec import get_hookspec

    if hooks:
        print("\nHook 详情:")
        for hook_name in hooks:
            spec = get_hookspec(hook_name)
            if spec:
                firstresult = "是" if spec.firstresult else "否"
                print(f"  • {info(hook_name)}")
                print(f"    - 首个结果返回: {firstresult}")
                print(f"    - 历史调用: {'是' if spec.historic else '否'}")

    print()
    return 0


def _plugin_enable(args: argparse.Namespace) -> int:
    """启用插件

    Args:
        args: 命令行参数（args.name 为插件名）

    Returns:
        退出码
    """
    if not args.name:
        print(error("缺少插件名称"))
        print(dim("用法: kb plugin enable <name>"))
        return 1

    pm = get_plugin_manager()
    plugins = pm.list_plugins()

    plugin_names = [p["name"] for p in plugins]
    if args.name not in plugin_names:
        print(error(f"插件不存在: {args.name}"))
        print(dim("使用 'kb plugin list' 查看所有插件"))
        return 1

    if pm.is_enabled(args.name):
        print(warning(f"插件已启用: {args.name}"))
        return 0

    pm.enable_plugin(args.name)
    print(success(f"插件已启用: {args.name}"))
    return 0


def _plugin_disable(args: argparse.Namespace) -> int:
    """禁用插件

    Args:
        args: 命令行参数（args.name 为插件名）

    Returns:
        退出码
    """
    if not args.name:
        print(error("缺少插件名称"))
        print(dim("用法: kb plugin disable <name>"))
        return 1

    pm = get_plugin_manager()
    plugins = pm.list_plugins()

    plugin_names = [p["name"] for p in plugins]
    if args.name not in plugin_names:
        print(error(f"插件不存在: {args.name}"))
        print(dim("使用 'kb plugin list' 查看所有插件"))
        return 1

    if not pm.is_enabled(args.name):
        print(warning(f"插件已禁用: {args.name}"))
        return 0

    pm.disable_plugin(args.name)
    print(success(f"插件已禁用: {args.name}"))
    return 0


def _plugin_load(args: argparse.Namespace) -> int:
    """手动加载插件文件

    Args:
        args: 命令行参数（args.path 为插件文件路径）

    Returns:
        退出码
    """
    if not args.path:
        print(error("缺少插件路径"))
        print(dim("用法: kb plugin load <path>"))
        return 1

    plugin_path = Path(args.path).expanduser()

    if not plugin_path.exists():
        print(error(f"文件不存在: {plugin_path}"))
        return 1

    if plugin_path.suffix != ".py":
        print(error(f"不是 Python 文件: {plugin_path}"))
        return 1

    pm = get_plugin_manager()

    # 生成模块名
    module_name = f"manual_plugin_{plugin_path.stem}"

    try:
        # 加载插件模块
        module = load_plugin_module(plugin_path, module_name)

        # 发现 hookimpl
        hookimpls = discover_hookimpls(module)

        if not hookimpls:
            print(warning(f"未发现 @hookimpl 标记的函数: {plugin_path.name}"))
            return 1

        # 注册插件
        plugin_name = plugin_path.stem
        pm._register_module(plugin_name, module, hookimpls)

        print(success(f"插件已加载: {plugin_name}"))

        # 显示注册的 hooks
        hooks_str = ", ".join(h[0] for h in hookimpls)
        print(f"  注册的 Hook: {info(hooks_str)}")

        return 0

    except SyntaxError as e:
        print(error(f"语法错误: {e}"))
        return 1
    except ImportError as e:
        print(error(f"导入错误: {e}"))
        return 1
    except Exception as e:
        print(error(f"加载失败: {e}"))
        return 1


def _load_plugins_from_settings() -> int:
    """从配置中加载插件（启动时调用）

    Returns:
        加载的插件数量
    """
    settings = get_settings()
    pm = get_plugin_manager()

    total_loaded = 0

    # 从目录加载
    for plugin_dir_str in settings.plugin_dirs:
        plugin_dir = Path(plugin_dir_str).expanduser()
        loaded = pm.load_from_directory(plugin_dir)
        total_loaded += len(loaded)

    # 应用启用/禁用配置
    for name in settings.plugins_enabled:
        pm.enable_plugin(name)

    for name in settings.plugins_disabled:
        pm.disable_plugin(name)

    # 从 entry_points 加载
    pm.load_from_entrypoints()

    return total_loaded


def setup_plugin_parser(subparsers) -> None:
    """设置 plugin 子命令解析器

    Args:
        subparsers: argparse subparsers 对象
    """
    parser_plugin = subparsers.add_parser(
        "plugin",
        help="插件管理",
        description="管理知识库插件，支持列表、详情、启用/禁用和手动加载",
    )

    plugin_subparsers = parser_plugin.add_subparsers(dest="plugin_command")

    # list 子命令
    plugin_subparsers.add_parser("list", help="列出所有已注册插件")

    # info 子命令
    parser_info = plugin_subparsers.add_parser("info", help="查看插件详情")
    parser_info.add_argument("name", help="插件名称")

    # enable 子命令
    parser_enable = plugin_subparsers.add_parser("enable", help="启用插件")
    parser_enable.add_argument("name", help="插件名称")

    # disable 子命令
    parser_disable = plugin_subparsers.add_parser("disable", help="禁用插件")
    parser_disable.add_argument("name", help="插件名称")

    # load 子命令
    parser_load = plugin_subparsers.add_parser("load", help="手动加载插件文件")
    parser_load.add_argument("path", help="插件文件路径")
