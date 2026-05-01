"""CLI serve 命令 — 启动 API 服务器"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def cmd_serve(args: Any) -> int:
    """启动 HTTP API 服务器

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

    host = getattr(args, "host", "0.0.0.0")
    port = getattr(args, "port", 8000)
    reload = getattr(args, "reload", False)

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
