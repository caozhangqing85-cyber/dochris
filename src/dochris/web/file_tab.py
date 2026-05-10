"""Tab 2: 文件管理 — 文件列表、搜索过滤、状态标签"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

import gradio as gr  # type: ignore[import-untyped]

from .utils import STATUS_FILTER_LABELS, STATUS_LABEL_REVERSE, get_manifest_data, get_settings

logger = logging.getLogger(__name__)


def _get_file_table(search: str = "", status_filter: str = "全部") -> list[list[str]]:
    """获取文件列表（用于 Dataframe 展示），支持搜索和过滤"""
    # 将中文标签还原为内部值
    internal_filter = STATUS_LABEL_REVERSE.get(status_filter, status_filter)
    manifests, _, _ = get_manifest_data()
    rows: list[list[str]] = []
    search_lower = search.lower().strip()

    for m in manifests:
        name = m.get("original_filename", m.get("source_file", "unknown"))
        file_type = m.get("type", "unknown")
        status = m.get("status", "unknown")
        quality = str(m.get("quality_score", "-"))
        manifest_id = m.get("id", "")

        if internal_filter != "全部" and status != internal_filter:
            continue
        if (
            search_lower
            and search_lower not in name.lower()
            and search_lower not in manifest_id.lower()
            and search_lower not in file_type.lower()
        ):
            continue

        rows.append([manifest_id, name, file_type, status, quality])
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


def handle_upload(files: list[Any]) -> str:
    """处理文件上传"""
    from dochris.core.utils import sanitize_filename

    if not files:
        return "*未选择文件*"
    settings = get_settings()
    raw_dir = settings.raw_dir
    raw_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in files:
        try:
            src = Path(f.name)
            safe_name = sanitize_filename(src.name)
            dst = raw_dir / safe_name
            if not dst.exists():
                shutil.copy2(src, dst)
                count += 1
        except Exception as e:
            # 文件上传守卫：单个文件失败不应中断整个上传批次
            logger.warning(f"上传文件 {f.name} 失败: {e}")
    return f"已上传 {count}/{len(files)} 个文件到 raw/ 目录"


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
            filter_btn = gr.Button("🔍 筛选", variant="secondary", scale=1)

        with gr.Row():
            upload_file = gr.File(
                label="上传文件（支持拖拽，多选）",
                file_count="multiple",
                scale=3,
            )
            file_status = gr.Markdown(value="*点击筛选或上传文件*")

        file_table = gr.Dataframe(
            headers=["ID", "文件名", "类型", "状态", "质量分"],
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
            outputs=file_status,
        )
