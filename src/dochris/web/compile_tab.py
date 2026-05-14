"""Tab 3: 编译控制 — 编译触发、进度显示、日志"""

from __future__ import annotations

import logging

import gradio as gr  # type: ignore[import-untyped]

from .utils import get_manifest_data

logger = logging.getLogger(__name__)

SUCCESS_STATUSES = {"compiled", "promoted_to_wiki", "promoted"}
FAILED_STATUSES = {"failed", "compile_failed"}

# 编译锁，防止并发编译
_compile_lock = False


def get_compile_info() -> str:
    """获取编译预览信息"""
    manifests, status_counter, _ = get_manifest_data()
    pending = status_counter.get("ingested", 0)
    compiled = status_counter.get("compiled", 0)
    failed = status_counter.get("failed", 0)
    return (
        f"**待编译:** {pending} | **已编译:** {compiled} | **失败:** {failed}"
        f" | **总计:** {len(manifests)}"
    )


def handle_compile(limit: int) -> str:
    """触发编译"""
    try:
        import asyncio

        from dochris.phases.phase2_compilation import compile_all

        pending_ids = _get_pending_ids(limit)
        asyncio.run(compile_all(limit=limit))
        stats = _count_finished_statuses(pending_ids)
        if stats["failed"]:
            return (
                f"**编译结束，但有失败** — 成功 {stats['success']} 个，"
                f"失败 {stats['failed']} 个，总计 {stats['total']} 个"
            )
        return f"**编译完成** — 成功 {stats['success']} 个，总计 {stats['total']} 个"
    except Exception as e:
        # UI 事件处理器顶层守卫
        logger.error(f"编译失败: {e}")
        return f"**编译出错:** {e}"


def _handle_compile_v2(limit: int, concurrency: int, dry_run: bool) -> tuple[str, str]:
    """增强版编译处理

    Returns:
        (编译结果, 编译预览信息)
    """
    global _compile_lock

    if _compile_lock:
        return "**编译正在进行中，请等待完成后再试**", get_compile_info()

    try:
        _compile_lock = True
        if dry_run:
            manifests, status_counter, _ = get_manifest_data()
            pending = status_counter.get("ingested", 0)
            to_compile = min(pending, limit) if limit else pending
            msg = f"**模拟运行** — 将编译 {to_compile} 个文件（并发: {concurrency}）"
            return msg, get_compile_info()

        import asyncio

        from dochris.phases.phase2_compilation import compile_all

        pending_ids = _get_pending_ids(limit)
        asyncio.run(compile_all(limit=limit, max_concurrent=concurrency))
        stats = _count_finished_statuses(pending_ids)
        if stats["failed"]:
            result_msg = (
                f"**编译结束，但有失败** — 成功 {stats['success']} 个，"
                f"失败 {stats['failed']} 个，总计 {stats['total']} 个（并发: {concurrency}）"
            )
        else:
            result_msg = (
                f"**编译完成** — 成功 {stats['success']} 个，"
                f"总计 {stats['total']} 个（并发: {concurrency}）"
            )
        return result_msg, get_compile_info()
    except Exception as e:
        # UI 事件处理器顶层守卫
        logger.error(f"编译失败: {e}")
        return f"**编译出错:** {e}", get_compile_info()
    finally:
        _compile_lock = False


def _get_pending_ids(limit: int | None) -> list[str]:
    """获取本次按钮点击预计处理的待编译文件 ID。"""
    manifests, _, _ = get_manifest_data()
    pending_ids = [m["id"] for m in manifests if m.get("status") == "ingested"]
    if limit:
        return pending_ids[:limit]
    return pending_ids


def _count_finished_statuses(src_ids: list[str]) -> dict[str, int]:
    """统计本次待编译文件的最终状态。"""
    manifests, _, _ = get_manifest_data()
    status_by_id = {m.get("id"): m.get("status") for m in manifests}
    success = sum(1 for src_id in src_ids if status_by_id.get(src_id) in SUCCESS_STATUSES)
    failed = sum(1 for src_id in src_ids if status_by_id.get(src_id) in FAILED_STATUSES)
    return {"total": len(src_ids), "success": success, "failed": failed}


def create_compile_tab() -> gr.Markdown:
    """创建编译控制 Tab，返回 compile_info 组件供 app.load 使用"""
    with gr.Tab("⚙️ 编译控制"):
        compile_info = gr.Markdown(value="*加载中...*")
        with gr.Row():
            compile_limit = gr.Slider(
                minimum=1,
                maximum=100,
                value=10,
                step=1,
                label="编译数量限制",
            )
            compile_concurrency = gr.Slider(
                minimum=1,
                maximum=5,
                value=1,
                step=1,
                label="并发数",
            )
        compile_dry_run = gr.Checkbox(label="模拟运行（不实际编译）", value=False)
        with gr.Row():
            compile_btn = gr.Button("▶️ 开始编译", variant="primary")
            compile_preview_btn = gr.Button("👁️ 刷新预览", variant="secondary")

        compile_output = gr.Markdown(
            label="编译结果",
            value="*设置编译参数后点击开始编译*",
        )

        compile_btn.click(
            fn=_handle_compile_v2,
            inputs=[compile_limit, compile_concurrency, compile_dry_run],
            outputs=[compile_output, compile_info],
        )
        compile_preview_btn.click(
            fn=get_compile_info,
            outputs=compile_info,
        )

    return compile_info
