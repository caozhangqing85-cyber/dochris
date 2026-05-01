"""状态路由 — GET /api/v1/status"""

from __future__ import annotations

import logging
from collections import Counter

from fastapi import APIRouter

from dochris import __version__
from dochris.api.schemas import ConfigInfo, ManifestStats, StatusResponse
from dochris.manifest import get_all_manifests
from dochris.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["status"])


@router.get("/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    """获取系统状态概览"""
    settings = get_settings()
    workspace = settings.workspace

    manifests = get_all_manifests(workspace)
    status_counter: Counter[str] = Counter(m.get("status", "unknown") for m in manifests)
    type_counter: Counter[str] = Counter(m.get("type", "unknown") for m in manifests)

    return StatusResponse(
        workspace=str(workspace),
        version=__version__,
        manifests=ManifestStats(
            total=len(manifests),
            ingested=status_counter.get("ingested", 0),
            compiled=status_counter.get("compiled", 0),
            failed=status_counter.get("failed", 0),
            promoted_to_wiki=status_counter.get("promoted_to_wiki", 0),
            promoted=status_counter.get("promoted", 0),
            by_type=dict(type_counter),
        ),
        config=ConfigInfo(
            model=settings.model,
            api_base=settings.api_base,
            max_concurrency=settings.max_concurrency,
            min_quality_score=settings.min_quality_score,
            has_api_key=bool(settings.api_key),
        ),
    )
