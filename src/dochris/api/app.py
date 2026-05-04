"""FastAPI 应用实例与路由挂载"""

from __future__ import annotations

import logging
import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dochris import __version__
from dochris.api.auth import verify_api_key

logger = logging.getLogger(__name__)


def _get_cors_origins() -> list[str]:
    """从环境变量获取允许的 CORS 来源"""
    env_origins = os.environ.get("DOCHRIS_CORS_ORIGINS", "")
    if env_origins:
        return [o.strip() for o in env_origins.split(",") if o.strip()]
    logger.warning(
        "CORS 使用默认 localhost 配置。生产环境请设置 DOCHRIS_CORS_ORIGINS 环境变量指定允许的来源。"
    )
    return [
        "http://localhost:8000",
        "http://localhost:7860",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:7860",
    ]


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例

    Returns:
        配置好的 FastAPI 实例
    """
    application = FastAPI(
        title="dochris API",
        description="知识库编译系统 REST API",
        version=__version__,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=_get_cors_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    )

    from dochris.api.routes.compile import router as compile_router
    from dochris.api.routes.graph import router as graph_router
    from dochris.api.routes.promote import router as promote_router
    from dochris.api.routes.query import router as query_router
    from dochris.api.routes.status import router as status_router

    # API 路由需要认证（开发模式下 DOCHRIS_API_KEY 为空则跳过）
    application.include_router(
        query_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)]
    )
    application.include_router(
        compile_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)]
    )
    application.include_router(
        status_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)]
    )
    application.include_router(
        promote_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)]
    )
    application.include_router(
        graph_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)]
    )

    @application.get("/", tags=["root"])
    async def root() -> dict[str, object]:
        """API 根路径欢迎页"""
        return {
            "name": "Dochris API",
            "version": __version__,
            "docs": "/docs",
            "health": "/health",
            "endpoints": {
                "query": "/api/v1/query",
                "status": "/api/v1/status",
                "compile": "/api/v1/compile",
                "promote": "/api/v1/promote/{src_id}",
                "graph": "/api/v1/graph",
            },
        }

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
