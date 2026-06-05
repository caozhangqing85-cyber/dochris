"""质量路由 — POST /api/v1/quality/reset"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from dochris.manifest import get_all_manifests, update_manifest_status
from dochris.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["quality"])


@router.post("/quality/reset")
async def reset_low_quality() -> dict[str, Any]:
    """重置低质量文件为待编译状态"""
    settings = get_settings()
    threshold = settings.min_quality_score
    workspace = settings.workspace
    manifests = get_all_manifests(workspace)
    reset_count = 0

    for m in manifests:
        qs = m.get("quality_score")
        status = m.get("status", "")
        src_id = m.get("id", "")
        if (
            qs is not None
            and isinstance(qs, (int, float))
            and int(qs) < threshold
            and status in ("compiled", "compile_failed")
            and src_id
        ):
            update_manifest_status(workspace, src_id, "ingested")
            reset_count += 1

    return {"reset_count": reset_count}
