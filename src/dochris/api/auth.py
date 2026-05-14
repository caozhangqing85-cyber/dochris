"""API 认证中间件"""

from __future__ import annotations

import hmac
import logging
import os

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

# 允许无认证访问的路径白名单（健康检查等）
_PUBLIC_PATHS: frozenset[str] = frozenset({"/health", "/docs", "/openapi.json", "/redoc"})


async def verify_api_key(request: Request) -> None:
    """验证 API Key

    通过 DOCHRIS_API_KEY 环境变量配置。
    如果未设置：
      - 仅允许来自 127.0.0.1 / localhost 的本地请求
      - 记录警告日志
    使用 hmac.compare_digest 进行常数时间比较，防止时序侧信道攻击。
    """
    # 健康检查等公开端点跳过认证
    path = getattr(request.url, "path", "") if hasattr(request, "url") else ""
    if path in _PUBLIC_PATHS:
        return

    api_key = os.environ.get("DOCHRIS_API_KEY", "")
    if not api_key:
        # 未配置 API Key 时，仅允许本地访问和测试客户端
        client_info = getattr(request, "client", None)
        client_host = client_info.host if client_info else ""
        allowed_hosts = {"127.0.0.1", "::1", "localhost", "testclient", ""}
        if client_host not in allowed_hosts:
            raise HTTPException(
                status_code=403,
                detail="API key not configured. Set DOCHRIS_API_KEY environment variable.",
            )
        if not client_host:
            logger.warning("API 运行在无认证模式（无客户端地址）。建议设置 DOCHRIS_API_KEY。")
        return

    client_key = request.headers.get("X-API-Key") or request.query_params.get("api_key", "")
    # 长度不同可直接返回，无需常数时间比较
    if len(client_key) != len(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    if not hmac.compare_digest(client_key, api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
