"""CLI serve 命令 — 启动 API 服务器"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def cmd_serve(args: Any) -> int:
    """启动 FastAPI HTTP API 服务器

    Args:
        args: argparse 解析后的参数，包含 host, port, reload

    Returns:
        退出码
    """
    try:
        import uvicorn
    except ImportError:
        print("错误: 需要安装 API 依赖。运行: pip install dochris[api]")
        return 1

    host = getattr(args, "host", "127.0.0.1")
    port = getattr(args, "port", 8000)
    reload = getattr(args, "reload", False)

    if _requires_api_key(host) and not os.environ.get("DOCHRIS_API_KEY"):
        print("错误: 监听非本机地址时必须设置 DOCHRIS_API_KEY")
        return 1

    logger.info(f"启动 dochris API 服务器: http://{host}:{port}")
    print(f"dochris API 服务器: http://{host}:{port}")
    print(f"API 文档: http://{host}:{port}/docs")
    print(f"健康检查: http://{host}:{port}/health")

    uvicorn.run(
        "dochris.api.app:app",
        host=host,
        port=port,
        reload=reload,
    )
    return 0


def _requires_api_key(host: str) -> bool:
    """判断监听地址是否需要显式 API Key 保护"""
    return host not in {"127.0.0.1", "localhost", "::1"}
