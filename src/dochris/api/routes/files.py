"""文件上传路由 — POST /api/v1/files/upload"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from dochris.core.error_sanitizer import sanitize_error_text
from dochris.core.utils import sanitize_filename
from dochris.manifest import (
    _workspace_write_lock,
    create_manifest,
    find_manifest_by_content_hash,
    get_all_manifests,
)
from dochris.phases.phase1_ingestion import file_hash
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

            # 独占创建（O_EXCL）：消除"解析路径→打开文件"窗口期的并发同名覆盖
            # （check-then-act 竞态会让两个 worker 交错写坏同一实体）
            managed_path: Path | None = None
            write_fd: int | None = None
            open_error: str | None = None
            exhausted = False
            stem, suffix = Path(original_name).stem, Path(original_name).suffix
            candidate = managed_dir / original_name
            for attempt in range(1000):
                try:
                    write_fd = os.open(str(candidate), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
                    managed_path = candidate
                    break
                except FileExistsError:
                    candidate = managed_dir / f"{stem}_{attempt + 1}{suffix}"
                except OSError as e:
                    # 脱敏：os.open 错误可能带绝对路径
                    failed.append(
                        f"{original_name}: {type(e).__name__}: {sanitize_error_text(str(e))}"
                    )
                    open_error = type(e).__name__
                    break
            if managed_path is None or write_fd is None:
                if open_error is None:
                    exhausted = True
                if exhausted:
                    failed.append(f"{original_name}: 文件名冲突过多")
                elif open_error is not None:
                    pass  # 错误已在循环内记录
                else:
                    failed.append(f"{original_name}: 文件打开失败")
                continue

            # 分块流式写入，边写边累计大小，超限即中止删除（防大文件 OOM）
            too_large = False
            written = 0
            with os.fdopen(write_fd, "wb") as f:
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

            # 跨进程原子判重+创建（P2：哈希查重与 manifest 创建必须同临界区，
            # 否则双 worker 并发上传相同内容会产生重复 manifest）。
            # 同步阻塞段放入线程池，避免 flock 等待阻塞事件循环。
            entity_path = managed_path
            entity_hash = content_hash
            entity_category = category
            entity_rel_path = rel_path

            def _dedupe_and_create(
                entity_path: Path = entity_path,
                entity_hash: str | None = entity_hash,
                entity_category: str = entity_category,
                entity_rel_path: str = entity_rel_path,
            ) -> Any | None:
                with _workspace_write_lock(workspace):
                    if entity_hash and find_manifest_by_content_hash(workspace, entity_hash):
                        return None
                    return create_manifest(
                        workspace_path=workspace,
                        src_id=None,
                        title=entity_path.name,
                        file_type=entity_category,
                        source_path=entity_path.resolve(),
                        file_path=entity_rel_path,
                        content_hash=entity_hash or "",
                        size_bytes=entity_path.stat().st_size,
                    )

            manifest = await asyncio.to_thread(_dedupe_and_create)

            if manifest is None:
                skipped += 1
                managed_path.unlink(missing_ok=True)
                continue

            logger.info(f"上传入库 {manifest['id']}: {managed_path.name}")
            existing_hashes.add(content_hash)
            saved += 1
            ingested += 1
        except Exception as e:
            logger.warning(f"上传文件失败: {e}")
            # 错误信息脱敏（不得向客户端泄漏本机绝对路径等内部细节）
            failed.append(f"{original_name}: {sanitize_error_text(str(e))}")

    return {
        "saved": saved,
        "ingested": ingested,
        "skipped": skipped,
        "failed": len(failed),
        "errors": failed[:5],
    }
