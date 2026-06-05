"""状态路由 — GET /api/v1/status"""

from __future__ import annotations

import logging
import platform
import shutil
import sys
from collections import Counter
from pathlib import Path

from fastapi import APIRouter

from dochris import __version__
from dochris.api.schemas import ConfigInfo, ManifestStats, StatusResponse, SystemInfo
from dochris.manifest import get_all_manifests
from dochris.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["status"])


def _count_files(directory: Path) -> int:
    """统计目录中的文件数量"""
    if not directory.is_dir():
        return 0
    return sum(1 for _ in directory.iterdir() if _.is_file())


@router.get("/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    """获取系统状态概览"""
    settings = get_settings()
    workspace = settings.workspace

    manifests = get_all_manifests(workspace)
    status_counter: Counter[str] = Counter(m.get("status", "unknown") for m in manifests)

    # "compile_failed" 也计入 failed
    failed_count = status_counter.get("failed", 0) + status_counter.get("compile_failed", 0)
    type_counter: Counter[str] = Counter(m.get("type", "unknown") for m in manifests)
    trust_counter: Counter[str] = Counter(
        m.get("trust_level") or "unrated" for m in manifests if m.get("status") == "compiled"
    )

    # 系统信息
    disk = shutil.disk_usage(str(workspace))
    system_info = SystemInfo(
        python_version=sys.version,
        platform=platform.platform(),
        disk_usage_bytes=disk.used,
        disk_total_bytes=disk.total,
    )

    # 知识库产出统计
    concepts_dir = workspace / "outputs" / "concepts"
    summaries_dir = workspace / "outputs" / "summaries"

    return StatusResponse(
        workspace=str(workspace),
        version=__version__,
        manifests=ManifestStats(
            total=len(manifests),
            ingested=status_counter.get("ingested", 0),
            compiled=status_counter.get("compiled", 0),
            failed=failed_count,
            promoted_to_wiki=status_counter.get("promoted_to_wiki", 0),
            promoted=status_counter.get("promoted", 0),
            by_type=dict(type_counter),
            trust_levels=dict(trust_counter),
            concepts_count=_count_files(concepts_dir),
            summaries_count=_count_files(summaries_dir),
        ),
        config=ConfigInfo(
            model=settings.model,
            api_base=settings.api_base,
            max_concurrency=settings.max_concurrency,
            min_quality_score=settings.min_quality_score,
            has_api_key=bool(settings.api_key),
            query_model=settings.query_model,
            llm_provider=settings.llm_provider,
            workspace=str(workspace),
            temperature=settings.llm_temperature,
        ),
        system=system_info,
    )
