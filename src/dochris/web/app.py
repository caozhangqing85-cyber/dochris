"""Gradio Web UI 主文件 — 6 个功能页面（增强版）"""

from __future__ import annotations

import logging
import time

import gradio as gr  # type: ignore[import-untyped]

from dochris import __version__

from .graph_tab import _handle_graph_refresh
from .quality_tab import (
    _get_low_quality_table,
    _get_quality_dashboard,
    _get_quality_distribution_df,
    _get_status_distribution_df,
    _get_type_distribution_df,
    _handle_recompile_low_quality,
)
from .utils import (
    _EMPTY_QUALITY_DF,
    _EMPTY_STATUS_DF,
    _EMPTY_TYPE_DF,
    _QUERY_MODE_LABELS,
    _STATUS_FILTER_LABELS,
    _do_query,
    _export_markdown,
    _format_query_results,
    _get_compile_info,
    _get_file_table,
    _get_system_status,
    handle_upload,
)

logger = logging.getLogger(__name__)


# ============================================================
# Gradio 事件处理函数（向后兼容版）
# ============================================================


def handle_query(query_str: str, top_k: int) -> str:
    """处理查询请求（简单模式）"""
    if not query_str.strip():
        return "*请输入查询内容*"
    try:
        t0 = time.time()
        result = _do_query(query_str, top_k)
        result["time_seconds"] = result.get("time_seconds", time.time() - t0)
        return _format_query_results(result)
    except Exception as e:
        logger.error(f"查询失败: {e}")
        return f"**查询出错:** {e}"


def handle_refresh_files() -> tuple[list[list[str]], str]:
    """刷新文件列表"""
    try:
        rows = _get_file_table()
        return rows, f"共 {len(rows)} 条记录（最多显示 200 条）"
    except Exception as e:
        logger.error(f"刷新文件列表失败: {e}")
        return [], f"刷新失败: {e}"


def handle_refresh_status() -> str:
    """刷新系统状态"""
    try:
        return _get_system_status()
    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        return f"**获取状态失败:** {e}"


def handle_refresh_quality() -> str:
    """刷新质量仪表盘"""
    try:
        return _get_quality_dashboard()
    except Exception as e:
        logger.error(f"获取质量数据失败: {e}")
        return f"**获取质量数据失败:** {e}"


def handle_compile(limit: int) -> str:
    """触发编译"""
    try:
        import asyncio

        from dochris.phases.phase2_compilation import compile_all

        asyncio.run(compile_all(limit=limit))
        return f"编译完成: 已处理最多 {limit} 个文件"
    except Exception as e:
        logger.error(f"编译失败: {e}")
        return f"**编译出错:** {e}"


# ============================================================
# Gradio 事件处理函数（增强版）
# ============================================================


def _handle_query_v2(
    query_str: str, top_k: int, query_mode: str, history_state: list[dict[str, str]]
) -> tuple[str, list[dict[str, str]], list[list[str]], str | None]:
    """增强版查询处理

    Returns:
        (结果Markdown, 更新后的历史, 历史表格数据, 导出文件路径)
    """
    if not query_str.strip():
        return "*请输入查询内容*", history_state, _history_to_table(history_state), None
    try:
        t0 = time.time()
        result = _do_query(query_str, top_k, mode=query_mode)
        result["time_seconds"] = result.get("time_seconds", time.time() - t0)
        formatted = _format_query_results(result)

        now = time.strftime("%H:%M:%S")
        total_results = (
            len(result.get("vector_results", []))
            + len(result.get("concepts", []))
            + len(result.get("summaries", []))
        )
        new_entry: dict[str, str] = {
            "time": now,
            "query": query_str[:50],
            "mode": query_mode,
            "results": str(total_results),
        }
        new_history = [new_entry, *history_state[:49]]

        export_path = _export_markdown(formatted, f"query_{now.replace(':', '')}")
        return formatted, new_history, _history_to_table(new_history), export_path
    except Exception as e:
        logger.error(f"查询失败: {e}")
        return f"**查询出错:** {e}", history_state, _history_to_table(history_state), None


def _history_to_table(history: list[dict[str, str]]) -> list[list[str]]:
    """将查询历史转换为表格数据"""
    return [
        [h.get("time", ""), h.get("query", ""), h.get("mode", ""), h.get("results", "")]
        for h in history
    ]


def _handle_filter_files(search: str, status_filter: str) -> tuple[list[list[str]], str]:
    """带过滤的文件列表刷新"""
    try:
        rows = _get_file_table(search=search, status_filter=status_filter)
        filter_desc = f"搜索='{search or '全部'}' 状态='{status_filter}'"
        return rows, f"{filter_desc} — 共 {len(rows)} 条记录（最多 200 条）"
    except Exception as e:
        logger.error(f"刷新文件列表失败: {e}")
        return [], f"刷新失败: {e}"


def _handle_compile_v2(limit: int, concurrency: int, dry_run: bool) -> tuple[str, str]:
    """增强版编译处理

    Returns:
        (编译结果, 编译预览信息)
    """
    try:
        if dry_run:
            from .utils import _get_manifest_data

            _, status_counter, _ = _get_manifest_data()
            pending = status_counter.get("ingested", 0)
            to_compile = min(pending, limit) if limit else pending
            msg = f"**模拟运行** — 将编译 {to_compile} 个文件（并发: {concurrency}）"
            return msg, _get_compile_info()

        import asyncio

        from dochris.phases.phase2_compilation import compile_all

        asyncio.run(compile_all(limit=limit, max_concurrent=concurrency))
        result_msg = f"**编译完成** — 已处理最多 {limit} 个文件（并发: {concurrency}）"
        return result_msg, _get_compile_info()
    except Exception as e:
        logger.error(f"编译失败: {e}")
        return f"**编译出错:** {e}", _get_compile_info()


# ============================================================
# Gradio 应用工厂
# ============================================================


def create_web_app() -> gr.Blocks:
    """创建 Gradio Web UI（增强版）

    Returns:
        gr.Blocks 实例
    """
    with gr.Blocks(title="dochris - 个人知识库") as app:
        gr.Markdown(
            f"# 📚 dochris 个人知识库 v{__version__}\n四阶段流水线: 摄入 → 编译 → 审核 → 分发"
        )

        with gr.Tabs():
            # ── Tab 1: 知识库查询（增强） ──
            with gr.Tab("🔍 知识库查询"):
                with gr.Row():
                    query_input = gr.Textbox(
                        label="查询问题",
                        placeholder="输入关键词或问题...",
                        lines=2,
                        scale=3,
                    )
                    with gr.Column(scale=1):
                        query_mode = gr.Dropdown(
                            choices=[(label, mode) for mode, label in _QUERY_MODE_LABELS.items()],
                            value="combined",
                            label="查询模式",
                        )
                        top_k_slider = gr.Slider(
                            minimum=1,
                            maximum=20,
                            value=5,
                            step=1,
                            label="返回结果数量 (top_k)",
                        )
                query_btn = gr.Button("🔍 查询", variant="primary")
                query_output = gr.Markdown(label="查询结果", value="*输入查询内容后点击查询*")

                with gr.Row():
                    export_btn = gr.Button("📥 导出当前结果", size="sm")
                    export_file = gr.File(label="导出文件", interactive=False)

                with gr.Accordion("📋 查询历史", open=False):
                    history_state = gr.State([])
                    query_history = gr.Dataframe(
                        headers=["时间", "查询内容", "模式", "结果数"],
                        label="本次会话查询历史",
                        interactive=False,
                        wrap=True,
                    )

                query_btn.click(
                    fn=_handle_query_v2,
                    inputs=[query_input, top_k_slider, query_mode, history_state],
                    outputs=[query_output, history_state, query_history, export_file],
                )
                export_btn.click(
                    fn=_export_markdown,
                    inputs=[query_output],
                    outputs=export_file,
                )

            # ── Tab 2: 文件管理（增强） ──
            with gr.Tab("📁 文件管理"):
                with gr.Row():
                    file_search = gr.Textbox(
                        label="搜索文件",
                        placeholder="输入文件名、ID 或类型...",
                        scale=3,
                    )
                    status_filter = gr.Dropdown(
                        choices=_STATUS_FILTER_LABELS,
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

            # ── Tab 3: 编译控制（增强） ──
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
                    fn=_get_compile_info,
                    outputs=compile_info,
                )

            # ── Tab 4: 系统状态（增强） ──
            with gr.Tab("📊 系统状态"):
                status_refresh_btn = gr.Button("🔄 刷新状态")
                status_output = gr.Markdown(value="*点击刷新加载状态*")
                with gr.Row():
                    type_chart = gr.BarPlot(
                        value=_EMPTY_TYPE_DF.copy(),
                        x="类型",
                        y="数量",
                        title="文件类型分布",
                        height=300,
                    )
                    status_chart = gr.BarPlot(
                        value=_EMPTY_STATUS_DF.copy(),
                        x="状态",
                        y="数量",
                        title="文件状态分布",
                        height=300,
                    )
                status_refresh_btn.click(
                    fn=lambda: (
                        _get_system_status(),
                        _get_type_distribution_df(),
                        _get_status_distribution_df(),
                    ),
                    outputs=[status_output, type_chart, status_chart],
                )

            # ── Tab 5: 质量仪表盘（增强） ──
            with gr.Tab("🎯 质量仪表盘"):
                quality_refresh_btn = gr.Button("🔄 刷新质量数据")
                quality_output = gr.Markdown(value="*点击刷新加载质量数据*")
                quality_chart = gr.BarPlot(
                    value=_EMPTY_QUALITY_DF.copy(),
                    x="分数段",
                    y="文件数",
                    title="质量评分分布",
                    height=300,
                )
                with gr.Accordion("⚠️ 低质量文件（点击展开）", open=False):
                    low_quality_table = gr.Dataframe(
                        headers=["ID", "文件名", "质量分", "状态"],
                        label="低质量文件列表",
                        interactive=False,
                        wrap=True,
                    )
                    recompile_btn = gr.Button("🔄 重置低质量文件为待编译", variant="secondary")
                    recompile_output = gr.Markdown()
                recompile_btn.click(
                    fn=_handle_recompile_low_quality,
                    outputs=recompile_output,
                )
                quality_refresh_btn.click(
                    fn=lambda: (
                        _get_quality_dashboard(),
                        _get_quality_distribution_df(),
                        _get_low_quality_table(),
                    ),
                    outputs=[quality_output, quality_chart, low_quality_table],
                )

            # ── Tab 6: 知识图谱 ──
            with gr.Tab("🕸️ 知识图谱"):
                graph_refresh_btn = gr.Button("加载知识图谱")
                graph_output = gr.HTML(
                    value=(
                        "<p style='color:#888;text-align:center;padding:40px;'>"
                        "点击「加载知识图谱」按钮开始可视化</p>"
                    ),
                    label="知识图谱可视化",
                )
                graph_refresh_btn.click(
                    fn=_handle_graph_refresh,
                    outputs=graph_output,
                )

        # 页面加载时刷新编译信息
        app.load(fn=_get_compile_info, outputs=compile_info)

    return app  # type: ignore[no-any-return]


def launch_web(server_name: str = "0.0.0.0", server_port: int = 7860) -> None:
    """启动 Gradio Web UI 服务器

    Args:
        server_name: 监听地址
        server_port: 监听端口
    """
    app = create_web_app()
    logger.info(f"启动 dochris Web UI: http://{server_name}:{server_port}")
    app.launch(
        server_name=server_name,
        server_port=server_port,
        theme=gr.themes.Soft(),
    )
