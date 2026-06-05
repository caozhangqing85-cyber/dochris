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
        "http://localhost:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:7860",
        "http://127.0.0.1:3000",
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
    from dochris.api.routes.config import router as config_router
    from dochris.api.routes.contribution import router as contribution_router
    from dochris.api.routes.files import router as files_router
    from dochris.api.routes.graph import router as graph_router
    from dochris.api.routes.manifests import router as manifests_router
    from dochris.api.routes.promote import router as promote_router
    from dochris.api.routes.quality import router as quality_router
    from dochris.api.routes.query import router as query_router
    from dochris.api.routes.recompile import router as recompile_router
    from dochris.api.routes.schema import router as schema_router
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
    application.include_router(
        manifests_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)]
    )
    application.include_router(
        config_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)]
    )
    application.include_router(
        files_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)]
    )
    application.include_router(
        quality_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)]
    )
    application.include_router(
        contribution_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)]
    )
    application.include_router(
        schema_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)]
    )
    application.include_router(
        recompile_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)]
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
                "candidates": "/api/v1/candidates",
                "schema_enrich": "/api/v1/schema/enrich",
                "schema_auto_tag": "/api/v1/schema/auto-tag",
                "schema_stale": "/api/v1/schema/stale",
                "recompile_status": "/api/v1/recompile/status",
                "recompile_stale": "/api/v1/recompile/stale",
            },
        }

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()


@app.on_event("startup")
async def _preload_embedding_model() -> None:
    """应用启动时预加载嵌入模型，避免首次查询时冷启动延迟"""
    import threading

    def _load() -> None:
        try:
            from dochris.vector.chromadb_store import _build_embedding_function

            _build_embedding_function("BAAI/bge-small-zh-v1.5")
            logger.info("Embedding model preloaded successfully")
        except Exception as exc:
            logger.warning(f"Embedding model preload skipped: {exc}")

    thread = threading.Thread(target=_load, daemon=True)
    thread.start()
