"""Schema Evolution API — 图谱驱动的 manifest 自动优化"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from dochris.quality.schema_evolution import (
    auto_tag_manifests,
    detect_stale_compilations,
    enrich_manifests_from_graph,
)
from dochris.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["schema"])


@router.post("/schema/enrich")
async def enrich_from_graph() -> dict[str, Any]:
    """从知识图谱反向丰富 manifest 元数据"""
    settings = get_settings()
    return enrich_manifests_from_graph(settings.workspace)


@router.post("/schema/auto-tag")
async def auto_tag() -> dict[str, Any]:
    """基于概念共现自动生成 manifest 标签"""
    settings = get_settings()
    return auto_tag_manifests(settings.workspace)


@router.get("/schema/stale")
async def check_stale() -> dict[str, Any]:
    """检测使用旧配置编译的 manifest"""
    settings = get_settings()
    return detect_stale_compilations(settings.workspace)
