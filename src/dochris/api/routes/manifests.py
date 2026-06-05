"""Manifest 路由 — GET /api/v1/manifests"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from dochris.manifest import get_all_manifests, update_manifest_status
from dochris.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["manifests"])


@router.get("/manifests")
async def list_manifests(
    limit: int = 100, offset: int = 0, status: str | None = None
) -> list[dict[str, Any]]:
    """获取 manifest 列表（支持分页和状态过滤）

    Args:
        limit: 返回数量上限（默认 100，最大 1000）
        offset: 偏移量
        status: 按状态过滤（如 compiled, ingested, failed）
    """
    settings = get_settings()
    all_manifests = get_all_manifests(settings.workspace, status=status)
    manifests = all_manifests[offset : offset + min(limit, 1000)]
    # 清理不可序列化的字段
    result = []
    for m in manifests:
        item: dict[str, Any] = {
            "id": m.get("id", ""),
            "title": m.get("title", ""),
            "type": m.get("type", "unknown"),
            "status": m.get("status", "unknown"),
            "quality_score": m.get("quality_score"),
            "trust_level": m.get("trust_level"),
            "file_path": m.get("file_path", ""),
            "size_bytes": m.get("size_bytes", 0),
            "original_filename": m.get("original_filename", m.get("title", "")),
            "error_message": m.get("error_message", ""),
        }
        # 保留编译摘要
        summary = m.get("compiled_summary") or m.get("summary")
        if isinstance(summary, dict):
            item["compiled_summary"] = {
                "one_line": summary.get("one_line", ""),
                "key_points": summary.get("key_points", []),
                "detailed_summary": summary.get("detailed_summary", ""),
                "concepts": summary.get("concepts", []),
                "quality_score": summary.get("quality_score"),
            }
        result.append(item)
    return result


@router.post("/manifests/reset-failed")
async def reset_failed_manifests() -> dict[str, Any]:
    """将所有失败文件重置为待编译状态"""
    settings = get_settings()
    workspace = settings.workspace
    manifests = get_all_manifests(workspace)
    reset_count = 0
    for m in manifests:
        if m.get("status") in ("failed", "compile_failed") and m.get("id"):
            update_manifest_status(workspace, m["id"], "ingested")
            reset_count += 1
    return {"reset_count": reset_count}
