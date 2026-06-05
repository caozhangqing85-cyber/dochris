"""Auto-Recompile API — 编译配置变更驱动的自动重编译"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query

from dochris.quality.auto_recompile import (
    get_recompile_status,
    trigger_stale_recompile,
)
from dochris.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["recompile"])


@router.get("/recompile/status")
async def recompile_status() -> dict[str, Any]:
    """获取重编译状态和陈旧 manifest 数量"""
    settings = get_settings()
    return get_recompile_status(settings.workspace)


@router.post("/recompile/stale")
async def recompile_stale(
    limit: int = Query(default=10, ge=1, le=100, description="最大重编译数量"),
    dry_run: bool = Query(default=False, description="模拟运行"),
) -> dict[str, Any]:
    """触发陈旧 manifest 的增量重编译

    只重编译编译配置指纹与当前配置不匹配的 manifest。
    """
    settings = get_settings()
    return trigger_stale_recompile(
        workspace_path=settings.workspace,
        limit=limit,
        dry_run=dry_run,
    )
