"""Tab 4: 系统状态 — 系统信息、知识库统计"""

from __future__ import annotations

import logging
import platform
import shutil

import gradio as gr  # type: ignore[import-untyped]
import pandas as pd  # type: ignore[import-untyped]

from dochris import __version__
from dochris.settings import get_settings

from .utils import EMPTY_STATUS_DF, EMPTY_TYPE_DF, get_manifest_data, sanitize_path

logger = logging.getLogger(__name__)


def get_system_status() -> str:
    """获取系统状态文本"""
    settings = get_settings()
    manifests, status_counter, type_counter = get_manifest_data()

    lines = [
        "## 系统信息",
        f"- **版本:** {__version__}",
        f"- **Python:** {platform.python_version()}",
        f"- **平台:** {platform.platform()}",
        f"- **工作区:** `{sanitize_path(settings.workspace)}`",
        f"- **LLM 模型:** {settings.model}",
        f"- **查询模型:** {settings.query_model}",
        f"- **API Base:** `{settings.api_base}`",
        f"- **API Key:** {'已配置' if settings.api_key else '未配置'}",
    ]

    try:
        disk = shutil.disk_usage(str(settings.workspace))
        total_gb = disk.total / (1024**3)
        used_gb = disk.used / (1024**3)
        free_gb = disk.free / (1024**3)
        pct = disk.used / disk.total * 100
        lines.append(
            f"- **磁盘:** {used_gb:.1f}/{total_gb:.1f}GB ({pct:.0f}%) — 剩余 {free_gb:.1f}GB"
        )
    except (OSError, ValueError):
        pass

    lines.extend(
        [
            "",
            "## 文件统计",
            f"- **总计:** {len(manifests)}",
            f"- **已摄入:** {status_counter.get('ingested', 0)}",
            f"- **已编译:** {status_counter.get('compiled', 0)}",
            f"- **已推广 (wiki):** {status_counter.get('promoted_to_wiki', 0)}",
            f"- **已推广 (curated):** {status_counter.get('promoted', 0)}",
            f"- **失败:** {status_counter.get('failed', 0)}",
        ]
    )

    # 知识库统计（概念数、摘要数）
    wiki_dir = settings.workspace / "wiki"
    concepts_count = 0
    summaries_count = 0
    try:
        concepts_dir = wiki_dir / "concepts"
        if concepts_dir.exists():
            concepts_count = sum(1 for p in concepts_dir.iterdir() if p.is_file())
        summaries_dir = wiki_dir / "summaries"
        if summaries_dir.exists():
            summaries_count = sum(1 for p in summaries_dir.iterdir() if p.is_file())
    except OSError:
        pass
    lines.extend(
        [
            "",
            "## 知识库统计",
            f"- **概念数:** {concepts_count}",
            f"- **摘要数:** {summaries_count}",
        ]
    )

    lines.extend(
        [
            "",
            "## 文件类型分布",
        ]
    )
    for ft, count in type_counter.most_common():
        lines.append(f"- **{ft}:** {count}")

    data_dir = settings.data_dir
    chroma_path = data_dir / "chroma.sqlite3"
    if chroma_path.exists():
        size_mb = chroma_path.stat().st_size / (1024 * 1024)
        lines.extend(
            [
                "",
                "## 向量数据库",
                f"- **路径:** `{sanitize_path(data_dir)}`",
                f"- **大小:** {size_mb:.1f} MB",
            ]
        )
    else:
        lines.extend(["", "## 向量数据库", "- **状态:** 未初始化"])

    lines.extend(["", "## 关键依赖"])
    for pkg in [
        "gradio",
        "chromadb",
        "pandas",
        "openai",
        "sentence_transformers",
        "markitdown",
        "json_repair",
        "rich",
    ]:
        try:
            mod = __import__(pkg)
            ver = getattr(mod, "__version__", "未知")
            display_name = pkg.replace("_", "-")
            lines.append(f"- **{display_name}:** {ver}")
        except ImportError:
            display_name = pkg.replace("_", "-")
            lines.append(f"- **{display_name}:** 未安装")

    return "\n".join(lines)


def _get_type_distribution_df() -> pd.DataFrame:
    """获取文件类型分布 DataFrame"""
    _, _, type_counter = get_manifest_data()
    if not type_counter:
        return EMPTY_TYPE_DF
    return pd.DataFrame(
        {"类型": list(type_counter.keys()), "数量": list(type_counter.values())}
    ).sort_values("数量", ascending=False)


def _get_status_distribution_df() -> pd.DataFrame:
    """获取文件状态分布 DataFrame"""
    _, status_counter, _ = get_manifest_data()
    if not status_counter:
        return EMPTY_STATUS_DF
    return pd.DataFrame(
        {"状态": list(status_counter.keys()), "数量": list(status_counter.values())}
    ).sort_values("数量", ascending=False)


def handle_refresh_status() -> str:
    """刷新系统状态"""
    try:
        return get_system_status()
    except Exception as e:
        # UI 事件处理器顶层守卫
        logger.error(f"获取系统状态失败: {e}")
        return f"**获取状态失败:** {e}"


def create_status_tab() -> None:
    """创建系统状态 Tab"""
    with gr.Tab("📊 系统状态"):
        status_refresh_btn = gr.Button("🔄 刷新状态")
        status_output = gr.Markdown(value="*点击刷新加载状态*")
        with gr.Row():
            type_chart = gr.BarPlot(
                value=EMPTY_TYPE_DF.copy(),
                x="类型",
                y="数量",
                title="文件类型分布",
                height=300,
            )
            status_chart = gr.BarPlot(
                value=EMPTY_STATUS_DF.copy(),
                x="状态",
                y="数量",
                title="文件状态分布",
                height=300,
            )
        status_refresh_btn.click(
            fn=lambda: (
                get_system_status(),
                _get_type_distribution_df(),
                _get_status_distribution_df(),
            ),
            outputs=[status_output, type_chart, status_chart],
        )
