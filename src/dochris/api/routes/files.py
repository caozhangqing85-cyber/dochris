"""文件上传路由 — POST /api/v1/files/upload"""

from __future__ import annotations

import logging
import os
import shutil
from typing import Any

from fastapi import APIRouter, File, UploadFile

from dochris.core.utils import sanitize_filename
from dochris.manifest import create_manifest, get_all_manifests, get_next_src_id
from dochris.phases.phase1_ingestion import file_hash, resolve_path_conflict
from dochris.settings import get_file_category, get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["files"])

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_FILES = 50


@router.post("/files/upload")
async def upload_files(files: list[UploadFile] = File(None)) -> dict[str, Any]:  # noqa: B008
    """上传文件到知识库"""
    if len(files) > MAX_FILES:
        return {"error": f"单次最多上传 {MAX_FILES} 个文件"}

    settings = get_settings()
    workspace = settings.workspace
    inbox_dir = workspace / "uploads" / "inbox"
    raw_dir = settings.raw_dir
    inbox_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    existing_hashes = {
        m.get("content_hash") for m in get_all_manifests(workspace) if m.get("content_hash")
    }

    saved = 0
    ingested = 0
    skipped = 0
    failed: list[str] = []

    for upload in files:
        try:
            original_name = sanitize_filename(upload.filename or "unknown")

            # 读取上传文件到临时位置
            inbox_dst = resolve_path_conflict(inbox_dir, original_name, logger)
            if inbox_dst is None:
                failed.append(f"{original_name}: 文件名冲突过多")
                continue

            with open(inbox_dst, "wb") as f:
                content = await upload.read()
                f.write(content)

            file_size = inbox_dst.stat().st_size
            if file_size > MAX_FILE_SIZE:
                failed.append(f"{original_name}: 文件过大")
                inbox_dst.unlink(missing_ok=True)
                continue

            if file_size == 0:
                failed.append(f"{original_name}: 空文件")
                inbox_dst.unlink(missing_ok=True)
                continue

            content_hash = file_hash(inbox_dst)
            if content_hash and content_hash in existing_hashes:
                skipped += 1
                inbox_dst.unlink(missing_ok=True)
                continue

            category = get_file_category(inbox_dst.suffix.lower())
            if category is None:
                failed.append(f"{original_name}: 不支持的文件类型")
                inbox_dst.unlink(missing_ok=True)
                continue

            managed_dir = raw_dir / category
            managed_dir.mkdir(parents=True, exist_ok=True)
            managed_path = resolve_path_conflict(managed_dir, inbox_dst.name, logger)
            if managed_path is None:
                failed.append(f"{original_name}: raw 目录冲突")
                continue

            # 优先符号链接
            try:
                os.symlink(str(inbox_dst.resolve()), str(managed_path))
            except (OSError, NotImplementedError):
                shutil.copy2(inbox_dst, managed_path)

            rel_path = str(managed_path.relative_to(workspace))
            src_id = get_next_src_id(workspace)
            create_manifest(
                workspace_path=workspace,
                src_id=src_id,
                title=inbox_dst.name,
                file_type=category,
                source_path=inbox_dst.resolve(),
                file_path=rel_path,
                content_hash=content_hash or "",
                size_bytes=inbox_dst.stat().st_size,
            )
            existing_hashes.add(content_hash)
            saved += 1
            ingested += 1
        except Exception as e:
            logger.warning(f"上传文件失败: {e}")
            failed.append(str(e))

    return {
        "saved": saved,
        "ingested": ingested,
        "skipped": skipped,
        "failed": len(failed),
        "errors": failed[:5],
    }
