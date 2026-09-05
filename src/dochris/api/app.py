"""FastAPI 应用实例与路由挂载"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from dochris import __version__
from dochris.api.auth import verify_api_key
from dochris.settings.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Run non-blocking startup work without deprecated event hooks."""
    await _preload_embedding_model()
    try:
        yield
    finally:
        compile_jobs = getattr(application.state, "compile_jobs", None)
        if compile_jobs is not None:
            await compile_jobs.close()


def _get_cors_origins() -> list[str]:
    """从环境变量获取允许的 CORS 来源"""
    env_origins = os.environ.get("DOCHRIS_CORS_ORIGINS", "")
    if env_origins:
        return [o.strip() for o in env_origins.split(",") if o.strip()]
    logger.warning(
        "CORS 使用默认 localhost 配置。生产环境请设置 DOCHRIS_CORS_ORIGINS 环境变量指定允许的来源。"
    )
    return [
        "http://localhost:3000",
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
        lifespan=_lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=_get_cors_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    )

    # 可观测性：trace_id 中间件（CORS → tracing → auth）
    from dochris.observability.middleware import TracingMiddleware

    application.add_middleware(TracingMiddleware)

    from dochris.api.routes.compile import router as compile_router
    from dochris.api.routes.config import router as config_router
    from dochris.api.routes.contribution import router as contribution_router
    from dochris.api.routes.files import router as files_router
    from dochris.api.routes.graph import router as graph_router
    from dochris.api.routes.manifests import router as manifests_router
    from dochris.api.routes.metrics import router as metrics_router
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

    # Prometheus /metrics 端点（无需认证，由 endpoint 自身检查开关）
    application.include_router(metrics_router, prefix="/api/v1")

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

    @application.get("/ready", tags=["health"])
    async def readiness(response: Response) -> dict[str, object]:
        """报告工作区是否满足 API 的最小运行条件。"""
        workspace = Path(get_settings().workspace).expanduser()
        required_directories = (
            "curated",
            "manifests/sources",
            "outputs",
            "raw",
            "wiki",
        )

        workspace_exists = workspace.is_dir()
        workspace_writable = workspace_exists and os.access(workspace, os.W_OK)
        missing = sorted(
            relative for relative in required_directories if not (workspace / relative).is_dir()
        )
        unwritable = sorted(
            relative
            for relative in required_directories
            if (workspace / relative).is_dir() and not os.access(workspace / relative, os.W_OK)
        )
        is_ready = workspace_exists and workspace_writable and not missing and not unwritable
        if not is_ready:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        workspace_status = (
            "missing" if not workspace_exists else "read_only" if not workspace_writable else "ok"
        )
        directories_status = "missing" if missing else "read_only" if unwritable else "ok"

        return {
            "status": "ready" if is_ready else "not_ready",
            "version": __version__,
            "checks": {
                "workspace": {
                    "status": workspace_status,
                    "path": str(workspace),
                    "writable": workspace_writable,
                },
                "directories": {
                    "status": directories_status,
                    "missing": missing,
                    "unwritable": unwritable,
                },
            },
        }

    return application


app = create_app()


async def _preload_embedding_model() -> None:
    """按需后台预加载嵌入模型，避免默认启动触发模型下载。"""
    preload_enabled = os.environ.get("DOCHRIS_PRELOAD_EMBEDDING", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not preload_enabled:
        logger.debug("Embedding preload disabled; set DOCHRIS_PRELOAD_EMBEDDING=true to enable it")
        return

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
