"""插件模块自动发现

提供动态加载和自动发现插件模块的功能。
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


def discover_hookimpls(module: Any) -> list[tuple[str, Callable]]:
    """扫描模块中所有 @hookimpl 标记的函数

    通过函数名与 hookspec 名称匹配来确定对应关系。

    Args:
        module: Python 模块对象

    Returns:
        [(hook_name, func), ...]

    Examples:
        >>> import my_plugin
        >>> discover_hookimpls(my_plugin)
        [('ingest_parser', <function my_plugin.ingest_parser>), ...]
    """
    hookimpls: list[tuple[str, Callable]] = []

    for name, obj in inspect.getmembers(module, inspect.isfunction):
        # 检查是否有 _is_hookimpl 标记
        if getattr(obj, "_is_hookimpl", False):
            # 函数名即为 hook 名称
            hookimpls.append((name, obj))
            logger.debug(f"Found hookimpl: {name} in {module.__name__}")

    return hookimpls


def load_plugin_module(module_path: Path, module_name: str) -> Any:
    """动态加载单个插件模块

    使用 importlib 加载 .py 文件为 Python 模块。

    Args:
        module_path: .py 文件路径
        module_name: 模块名称（用于 sys.modules 注册）

    Returns:
        模块对象

    Raises:
        ImportError: 加载失败
        SyntaxError: 语法错误
    """
    spec = importlib.util.spec_from_file_location(module_name, str(module_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create spec for {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception:
        # 清理失败的模块
        if module_name in sys.modules:
            del sys.modules[module_name]
        raise

    return module


def load_plugin_from_code(code: str, module_name: str) -> Any:
    """从代码字符串加载插件模块

    Args:
        code: Python 代码字符串
        module_name: 模块名称

    Returns:
        模块对象

    Raises:
        ImportError: 加载失败
    """
    import types

    module = types.ModuleType(module_name)
    sys.modules[module_name] = module

    try:
        safe_builtins = {
            "print": print,
            "range": range,
            "len": len,
            "dict": dict,
            "list": list,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "True": True,
            "False": False,
            "None": None,
            "tuple": tuple,
            "set": set,
            "frozenset": frozenset,
            "type": type,
            "isinstance": isinstance,
            "issubclass": issubclass,
            "getattr": getattr,
            "hasattr": hasattr,
            "setattr": setattr,
            "Exception": Exception,
            "ValueError": ValueError,
            "TypeError": TypeError,
            "KeyError": KeyError,
            "AttributeError": AttributeError,
            "RuntimeError": RuntimeError,
            "NotImplementedError": NotImplementedError,
            "ImportError": ImportError,
        }
        exec(code, {"__builtins__": safe_builtins}, module.__dict__)  # noqa: S102
    except Exception:
        if module_name in sys.modules:
            del sys.modules[module_name]
        raise

    return module
