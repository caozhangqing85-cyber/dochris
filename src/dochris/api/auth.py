"""API 认证中间件"""

from __future__ import annotations

import hmac
import os

from fastapi import HTTPException, Request


async def verify_api_key(request: Request) -> None:
    """验证 API Key

    通过 DOCHRIS_API_KEY 环境变量配置。
    如果未设置，跳过认证（开发模式）。
    使用 hmac.compare_digest 进行常数时间比较，防止时序侧信道攻击。
    """
    api_key = os.environ.get("DOCHRIS_API_KEY", "")
    if not api_key:
        return  # 开发模式，无需认证

    client_key = (
        request.headers.get("X-API-Key")
        or request.query_params.get("api_key", "")
    )
    # 长度不同可直接返回，无需常数时间比较
    if len(client_key) != len(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    if not hmac.compare_digest(client_key, api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
