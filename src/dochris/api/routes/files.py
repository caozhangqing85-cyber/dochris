"""文件上传路由 — POST /api/v1/files/upload"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from dochris.core.utils import sanitize_filename
from dochris.manifest import create_manifest, get_all_manifests
from dochris.phases.phase1_ingestion import file_hash, resolve_path_conflict
from dochris.settings import get_file_category, get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["files"])

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_FILES = 50


@router.post("/files/upload", response_model=None)
async def upload_files(files: list[UploadFile] = File(None)) -> dict[str, Any] | JSONResponse:  # noqa: B008
    """上传文件到知识库"""
    if not files:
        return JSONResponse(
            status_code=400,
            content={"error": "未收到任何文件（需要 multipart/form-data 编码）"},
        )
    if len(files) > MAX_FILES:
        return JSONResponse(
            status_code=413,
            content={"error": f"单次最多上传 {MAX_FILES} 个文件"},
        )

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

            # Content-Length 预检：写盘前拒绝超大文件（防 OOM/磁盘耗尽）
            declared_size = upload.size if hasattr(upload, "size") else None
            if declared_size is not None and declared_size > MAX_FILE_SIZE:
                failed.append(f"{original_name}: 文件过大（{declared_size} 字节）")
                continue

            # 实体文件直接写入持久卷 raw/<category>/（修复容器重建后
            # uploads 丢失导致 raw 软链断链的数据丢失风险）；
            # uploads/inbox 仅保留指向 raw 的软链以兼容 inbox 工作流。
            category = get_file_category(Path(original_name).suffix.lower())
            if category is None:
                failed.append(f"{original_name}: 不支持的文件类型")
                continue

            managed_dir = raw_dir / category
            managed_dir.mkdir(parents=True, exist_ok=True)
            managed_path = resolve_path_conflict(managed_dir, original_name, logger)
            if managed_path is None:
                failed.append(f"{original_name}: raw 目录冲突")
                continue

            # 分块流式写入，边写边累计大小，超限即中止删除（防大文件 OOM）
            too_large = False
            written = 0
            with open(managed_path, "wb") as f:
                while True:
                    chunk = await upload.read(1024 * 1024)  # 1MB 分块
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > MAX_FILE_SIZE:
                        too_large = True
                        break
                    f.write(chunk)

            if too_large:
                failed.append(f"{original_name}: 文件过大")
                managed_path.unlink(missing_ok=True)
                continue

            file_size = written
            if file_size == 0:
                failed.append(f"{original_name}: 空文件")
                managed_path.unlink(missing_ok=True)
                continue

            content_hash = file_hash(managed_path)
            if content_hash and content_hash in existing_hashes:
                skipped += 1
                managed_path.unlink(missing_ok=True)
                continue

            # inbox 软链指向 raw 实体（方向与旧版相反：raw 才是持久真身）
            inbox_dst = inbox_dir / managed_path.name
            if not inbox_dst.exists():
                try:
                    os.symlink(str(managed_path.resolve()), str(inbox_dst))
                except OSError:
                    logger.debug(f"inbox 软链创建失败（不影响数据）: {inbox_dst.name}")

            rel_path = str(managed_path.relative_to(workspace))
            # src_id=None：在跨进程写锁内自动分配，防多 worker 竞争覆盖
            manifest = create_manifest(
                workspace_path=workspace,
                src_id=None,
                title=managed_path.name,
                file_type=category,
                source_path=managed_path.resolve(),
                file_path=rel_path,
                content_hash=content_hash or "",
                size_bytes=managed_path.stat().st_size,
            )
            logger.info(f"上传入库 {manifest['id']}: {managed_path.name}")
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
