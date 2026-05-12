"""Tab 1: 知识库查询 — 查询历史、结果格式化、导出"""

from __future__ import annotations

import logging
import tempfile
import time
from datetime import datetime
from typing import Any

import gradio as gr  # type: ignore[import-untyped]

from .utils import QUERY_MODE_LABELS

logger = logging.getLogger(__name__)


def _do_query(query_str: str, top_k: int, mode: str = "combined") -> dict[str, Any]:
    """执行查询"""
    from dochris.phases.phase3_query import query

    return query(query_str, mode=mode, top_k=top_k)


def _format_query_results(result: dict[str, Any]) -> str:
    """格式化查询结果为 Markdown"""
    lines: list[str] = []
    elapsed = result.get("time_seconds", 0)
    mode = result.get("mode", "combined")
    lines.append(f"**查询耗时:** {elapsed:.2f}s | **模式:** {QUERY_MODE_LABELS.get(mode, mode)}\n")

    answer = result.get("answer")
    if answer:
        lines.append("## AI 回答\n")
        lines.append(f"{answer}\n")

    vector_results = result.get("vector_results", [])
    if vector_results:
        lines.append("## 向量搜索结果\n")
        for i, r in enumerate(vector_results, 1):
            score = r.get("score", 0)
            title = r.get("title", "无标题")
            content = r.get("content", "")
            source = r.get("source", "")
            src_id = r.get("manifest_id", "")
            lines.append(f"### {i}. {title} (相似度: {score:.3f})")
            if source:
                lines.append(f"**来源:** `{source}`\n")
            if src_id:
                lines.append(f"**Manifest:** `{src_id}`\n")
            if content:
                display = content[:500] + "..." if len(content) > 500 else content
                lines.append(f"> {display}\n")

    concepts = result.get("concepts", [])
    if concepts:
        lines.append("## 概念匹配\n")
        for i, c in enumerate(concepts, 1):
            name = c.get("name", c.get("title", ""))
            lines.append(f"{i}. **{name}**")

    summaries = result.get("summaries", [])
    if summaries:
        lines.append("## 摘要匹配\n")
        for i, s in enumerate(summaries, 1):
            title = s.get("title", "无标题")
            source = s.get("source", "")
            lines.append(f"{i}. **{title}**")
            if source:
                lines.append(f"   - 来源: `{source}`")

    if not vector_results and not concepts and not summaries and not answer:
        lines.append("*未找到相关结果*")

    return "\n".join(lines)


def _history_to_table(history: list[dict[str, str]]) -> list[list[str]]:
    """将查询历史转换为表格数据"""
    return [
        [h.get("time", ""), h.get("query", ""), h.get("mode", ""), h.get("results", "")]
        for h in history
    ]


def _export_markdown(content: str, prefix: str = "export") -> str | None:
    """将 Markdown 内容导出到临时文件"""
    content = (content or "").strip()
    placeholder_values = {
        "*输入查询内容后点击查询*",
        "*请输入查询内容*",
    }
    if not content or content in placeholder_values:
        return None
    try:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", prefix=prefix, delete=False, encoding="utf-8"
        )
        tmp.write(
            f"# 知识库查询结果\n\n导出时间:"
            f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n{content}"
        )
        tmp.close()
        return tmp.name
    except Exception as e:
        # 临时文件创建守卫：导出失败不应影响主流程
        logger.warning(f"导出失败: {e}")
        return None


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
        # UI 事件处理器顶层守卫
        logger.error(f"查询失败: {e}")
        return f"**查询出错:** {e}"


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

        now = datetime.now().strftime("%H:%M:%S")
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
        # UI 事件处理器顶层守卫
        logger.error(f"查询失败: {e}")
        return f"**查询出错:** {e}", history_state, _history_to_table(history_state), None


def create_query_tab() -> None:
    """创建知识库查询 Tab"""
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
                    choices=[(label, mode) for mode, label in QUERY_MODE_LABELS.items()],
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
