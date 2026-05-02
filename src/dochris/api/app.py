"""FastAPI 应用实例与路由挂载"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例

    Returns:
        配置好的 FastAPI 实例
    """
    application = FastAPI(
        title="dochris API",
        description="知识库编译系统 REST API",
        version="1.0.0",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from dochris.api.routes.compile import router as compile_router
    from dochris.api.routes.graph import router as graph_router
    from dochris.api.routes.promote import router as promote_router
    from dochris.api.routes.query import router as query_router
    from dochris.api.routes.status import router as status_router

    application.include_router(query_router, prefix="/api/v1")
    application.include_router(compile_router, prefix="/api/v1")
    application.include_router(status_router, prefix="/api/v1")
    application.include_router(promote_router, prefix="/api/v1")
    application.include_router(graph_router, prefix="/api/v1")

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
