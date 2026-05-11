"""CLI serve 命令 — 启动 API 服务器或 Gradio Web UI"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def cmd_serve(args: Any) -> int:
    """启动 HTTP API 服务器或 Gradio Web UI

    Args:
        args: argparse 解析后的参数，包含 host, port, reload, web

    Returns:
        退出码
    """
    use_web = getattr(args, "web", False)

    if use_web:
        return _launch_web(args)

    return _launch_api(args)


def _launch_api(args: Any) -> int:
    """启动 FastAPI 服务器"""
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


def _launch_web(args: Any) -> int:
    """启动 Gradio Web UI（挂载到 FastAPI 上，一个端口同时服务 API + Web UI）"""
    try:
        import gradio as gr  # type: ignore[import-untyped]
        import uvicorn
    except ImportError:
        print("错误: 需要安装 Web 依赖。运行: pip install dochris[web]")
        return 1

    from dochris.api.app import create_app
    from dochris.web.app import create_web_app

    host = getattr(args, "host", "127.0.0.1")
    port = getattr(args, "web_port", 7860)

    if _requires_api_key(host) and not os.environ.get("DOCHRIS_API_KEY"):
        print("错误: 监听非本机地址时必须设置 DOCHRIS_API_KEY")
        return 1

    fastapi_app = create_app()
    gradio_app = create_web_app()

    # Gradio 挂载到 FastAPI；使用返回的 app 保留 Gradio 注入的挂载状态。
    fastapi_app = gr.mount_gradio_app(
        fastapi_app,
        gradio_app,
        path="/ui",
        server_name=host,
        server_port=port,
    )

    logger.info(f"启动 dochris 统一服务: http://{host}:{port}")
    print(f"dochris 统一服务: http://{host}:{port}")
    print(f"Web UI: http://{host}:{port}/ui")
    print(f"API 文档: http://{host}:{port}/docs")
    print(f"健康检查: http://{host}:{port}/health")

    uvicorn.run(fastapi_app, host=host, port=port)
    return 0


def _requires_api_key(host: str) -> bool:
    """判断监听地址是否需要显式 API Key 保护"""
    return host not in {"127.0.0.1", "localhost", "::1"}
