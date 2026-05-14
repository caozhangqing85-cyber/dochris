"""Tab 2: 文件管理 — 文件列表、搜索过滤、状态标签"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any

import gradio as gr  # type: ignore[import-untyped]

from .utils import STATUS_FILTER_LABELS, STATUS_LABEL_REVERSE, get_manifest_data, get_settings

logger = logging.getLogger(__name__)


def _get_file_table(search: str = "", status_filter: str = "全部") -> list[list[str]]:
    """获取文件列表（用于 Dataframe 展示），支持搜索和过滤"""
    manifests, _, _ = get_manifest_data()
    return _manifest_rows(manifests, search=search, status_filter=status_filter)


def _manifest_rows(
    manifests: list[dict[str, Any]], search: str = "", status_filter: str = "全部"
) -> list[list[str]]:
    """将 manifest 列表转换为文件表格行"""
    # 将中文标签还原为内部值
    internal_filter = STATUS_LABEL_REVERSE.get(status_filter, status_filter)
    rows: list[list[str]] = []
    search_lower = search.lower().strip()

    for m in manifests:
        name = _manifest_display_name(m)
        file_type = m.get("type", "unknown")
        status = m.get("status", "unknown")
        quality = str(m.get("quality_score", "-"))
        manifest_id = m.get("id", "")
        file_path = m.get("file_path", "")

        if internal_filter != "全部" and status != internal_filter:
            continue
        if (
            search_lower
            and search_lower not in name.lower()
            and search_lower not in manifest_id.lower()
            and search_lower not in file_type.lower()
            and search_lower not in str(file_path).lower()
        ):
            continue

        rows.append([manifest_id, name, file_type, status, quality, file_path])
        if len(rows) >= 200:
            break
    return rows


def handle_refresh_files() -> tuple[list[list[str]], str]:
    """刷新文件列表"""
    try:
        rows = _get_file_table()
        return rows, f"共 {len(rows)} 条记录（最多显示 200 条）"
    except Exception as e:
        # UI 事件处理器顶层守卫
        logger.error(f"刷新文件列表失败: {e}")
        return [], f"刷新失败: {e}"


def handle_upload(files: list[Any]) -> tuple[list[list[str]], str]:
    """上传文件并立即登记为待编译文档"""
    from dochris.core.utils import sanitize_filename
    from dochris.manifest import create_manifest, get_all_manifests, get_next_src_id
    from dochris.phases.phase1_ingestion import file_hash, resolve_path_conflict
    from dochris.settings import get_file_category

    if not files:
        return _get_file_table(), "*未选择文件*"

    # 上传限制
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    MAX_FILES_PER_BATCH = 50
    ALLOWED_EXTENSIONS: frozenset[str] = frozenset({
        ".pdf", ".md", ".txt", ".docx", ".doc", ".pptx", ".xlsx",
        ".epub", ".mobi", ".azw3",
        ".mp3", ".wav", ".m4a", ".flac", ".ogg",
        ".mp4", ".mkv", ".avi", ".mov",
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp",
        ".py", ".js", ".ts", ".java", ".go", ".rs", ".c", ".cpp", ".h",
        ".json", ".yaml", ".yml", ".toml", ".csv",
    })

    if len(files) > MAX_FILES_PER_BATCH:
        return _get_file_table(), f"*单次最多上传 {MAX_FILES_PER_BATCH} 个文件*"

    settings = get_settings()
    workspace = settings.workspace
    inbox_dir = workspace / "uploads" / "inbox"
    raw_dir = settings.raw_dir
    inbox_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    existing_hashes = {
        m.get("content_hash")
        for m in get_all_manifests(workspace)
        if m.get("content_hash")
    }
    saved = 0
    ingested = 0
    skipped = 0
    failed: list[str] = []
    stored_paths: list[str] = []

    for f in files:
        try:
            src = _uploaded_file_path(f)
            original_name = sanitize_filename(_uploaded_original_name(f, src.name))
            if not src.exists():
                failed.append(f"{original_name}: 上传临时文件不存在")
                continue

            # 文件大小检查
            file_size = src.stat().st_size
            if file_size > MAX_FILE_SIZE:
                failed.append(f"{original_name}: 文件过大 ({file_size // 1024 // 1024}MB，上限 100MB)")
                continue

            # 文件类型检查
            ext = Path(original_name).suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                failed.append(f"{original_name}: 不支持的文件类型 ({ext})")
                continue

            # 空文件检查
            if file_size == 0:
                failed.append(f"{original_name}: 空文件，跳过")
                continue

            inbox_dst = resolve_path_conflict(inbox_dir, original_name, logger)
            if inbox_dst is None:
                failed.append(f"{original_name}: 文件名冲突过多")
                continue
            shutil.copy2(src, inbox_dst)
            saved += 1

            content_hash = file_hash(inbox_dst)
            if content_hash and content_hash in existing_hashes:
                skipped += 1
                stored_paths.append(_relative_to_workspace(inbox_dst, workspace))
                continue

            category = get_file_category(inbox_dst.suffix.lower())
            if category is None:
                failed.append(f"{original_name}: 不支持的文件类型")
                continue

            managed_dir = raw_dir / category
            managed_dir.mkdir(parents=True, exist_ok=True)
            managed_path = resolve_path_conflict(managed_dir, inbox_dst.name, logger)
            if managed_path is None:
                failed.append(f"{original_name}: raw 目录文件名冲突过多")
                continue

            _link_or_copy(inbox_dst, managed_path)
            rel_managed_path = _relative_to_workspace(managed_path, workspace)
            src_id = get_next_src_id(workspace)
            create_manifest(
                workspace_path=workspace,
                src_id=src_id,
                title=inbox_dst.name,
                file_type=category,
                source_path=inbox_dst.resolve(),
                file_path=rel_managed_path,
                content_hash=content_hash or "",
                size_bytes=inbox_dst.stat().st_size,
            )
            existing_hashes.add(content_hash)
            stored_paths.append(rel_managed_path)
            ingested += 1
        except Exception as e:
            # 文件上传守卫：单个文件失败不应中断整个上传批次
            logger.warning(f"上传文件失败: {e}")
            failed.append(str(e))

    rows = _manifest_rows(get_all_manifests(workspace))
    status_lines = [
        f"上传 {saved}/{len(files)} 个文件，新增待编译 {ingested} 个，重复跳过 {skipped} 个。",
        f"工作区: `{workspace}`",
    ]
    if stored_paths:
        status_lines.append("保存位置:")
        status_lines.extend(f"- `{p}`" for p in stored_paths[:5])
        if len(stored_paths) > 5:
            status_lines.append(f"- ...共 {len(stored_paths)} 个文件")
    if failed:
        status_lines.append("失败:")
        status_lines.extend(f"- {msg}" for msg in failed[:5])
        if len(failed) > 5:
            status_lines.append(f"- ...共 {len(failed)} 个失败")
    status_lines.append("下一步: 打开「编译控制」，点击「刷新预览」，然后点击「开始编译」。")
    return rows, "\n".join(status_lines)


def _handle_filter_files(search: str, status_filter: str) -> tuple[list[list[str]], str]:
    """带过滤的文件列表刷新"""
    try:
        rows = _get_file_table(search=search, status_filter=status_filter)
        filter_desc = f"搜索='{search or '全部'}' 状态='{status_filter}'"
        return rows, f"{filter_desc} — 共 {len(rows)} 条记录（最多 200 条）"
    except Exception as e:
        # UI 事件处理器顶层守卫
        logger.error(f"刷新文件列表失败: {e}")
        return [], f"刷新失败: {e}"


def _manifest_display_name(manifest: dict[str, Any]) -> str:
    """按优先级提取页面展示文件名"""
    for key in ("original_filename", "title", "source_file", "file_path", "source_path"):
        value = manifest.get(key)
        if value:
            return Path(str(value)).name
    return "unknown"


def _uploaded_file_path(uploaded_file: Any) -> Path:
    """兼容 Gradio 不同版本的上传文件对象"""
    if isinstance(uploaded_file, (str, Path)):
        return Path(uploaded_file)
    if isinstance(uploaded_file, dict):
        path = uploaded_file.get("path") or uploaded_file.get("name")
        if path:
            return Path(path)
    name = getattr(uploaded_file, "name", None)
    if name:
        return Path(name)
    path = getattr(uploaded_file, "path", None)
    if path:
        return Path(path)
    raise ValueError("无法识别上传文件路径")


def _uploaded_original_name(uploaded_file: Any, fallback: str) -> str:
    """获取用户上传时的原始文件名，避免使用 Gradio 临时文件名"""
    if isinstance(uploaded_file, dict):
        value = uploaded_file.get("orig_name") or uploaded_file.get("original_name")
        if value:
            return Path(str(value)).name
    for attr in ("orig_name", "original_name"):
        value = getattr(uploaded_file, attr, None)
        if value:
            return Path(str(value)).name
    return Path(fallback).name


def _relative_to_workspace(path: Path, workspace: Path) -> str:
    """返回相对工作区路径；不在工作区内时记录警告并返回文件名"""
    try:
        resolved = path.resolve()
        ws_resolved = workspace.resolve()
        rel = resolved.relative_to(ws_resolved)
        # 二次校验：确保 resolve 后仍在工作区内
        if not str(resolved).startswith(str(ws_resolved)):
            logger.warning(f"路径遍历检测: {path} 不在工作区 {workspace} 内")
            return path.name
        return str(rel)
    except ValueError:
        logger.warning(f"路径 {path} 不在工作区 {workspace} 内")
        return path.name


def _link_or_copy(src: Path, dst: Path) -> None:
    """优先创建符号链接，失败时复制文件

    Windows 上 os.symlink 可能因权限不足失败（需要管理员权限或开发者模式），
    自动降级为 shutil.copy2。
    """
    try:
        os.symlink(str(src.resolve()), str(dst))
    except (OSError, NotImplementedError):
        # NotImplementedError: Windows 不支持 symlink（罕见）
        shutil.copy2(src, dst)


def create_file_tab() -> None:
    """创建文件管理 Tab"""
    with gr.Tab("📁 文件管理"):
        with gr.Row():
            file_search = gr.Textbox(
                label="搜索文件",
                placeholder="输入文件名、ID 或类型...",
                scale=3,
            )
            status_filter = gr.Dropdown(
                choices=STATUS_FILTER_LABELS,
                value="全部",
                label="状态筛选",
                scale=1,
            )
            filter_btn = gr.Button("🔍 刷新/筛选", variant="secondary", scale=1)

        with gr.Row():
            upload_file = gr.File(
                label="上传文件（支持拖拽，多选）",
                file_count="multiple",
                scale=3,
            )
            file_status = gr.Markdown(value="*点击筛选或上传文件*")

        file_table = gr.Dataframe(
            headers=["ID", "文件名", "类型", "状态", "质量分", "保存路径"],
            label="文件列表",
            interactive=False,
            wrap=True,
        )

        filter_btn.click(
            fn=_handle_filter_files,
            inputs=[file_search, status_filter],
            outputs=[file_table, file_status],
        )
        upload_file.change(
            fn=handle_upload,
            inputs=[upload_file],
            outputs=[file_table, file_status],
        )
