"""Tab 5: 质量仪表盘 — 质量评分、分布统计"""

from __future__ import annotations

import json
import logging

import gradio as gr  # type: ignore[import-untyped]
import pandas as pd  # type: ignore[import-untyped]

from dochris.manifest import get_all_manifests
from dochris.settings import get_settings

from .utils import EMPTY_QUALITY_DF, STATUS_LABELS, get_manifest_data

logger = logging.getLogger(__name__)


def _get_quality_dashboard() -> str:
    """获取质量仪表盘数据"""
    manifests, _, _ = get_manifest_data()

    scores: list[int] = []
    low_quality: list[str] = []
    settings = get_settings()
    threshold = settings.min_quality_score

    for m in manifests:
        qs = m.get("quality_score")
        if qs is not None and isinstance(qs, (int, float)):
            score_int = int(qs)
            scores.append(score_int)
            if score_int < threshold:
                name = m.get("original_filename", m.get("source_file", "unknown"))
                low_quality.append(f"- `{name}` — 分数: {score_int}")

    if not scores:
        return "*暂无质量评分数据*"

    avg_score = sum(scores) / len(scores)
    below_threshold = len(low_quality)
    above_threshold = len(scores) - below_threshold

    buckets: dict[str, int] = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
    for s in scores:
        if s <= 20:
            buckets["0-20"] += 1
        elif s <= 40:
            buckets["21-40"] += 1
        elif s <= 60:
            buckets["41-60"] += 1
        elif s <= 80:
            buckets["61-80"] += 1
        else:
            buckets["81-100"] += 1

    lines = [
        "## 质量概览",
        f"- **已评分文件数:** {len(scores)}",
        f"- **平均分:** {avg_score:.1f}",
        f"- **最高分:** {max(scores)}",
        f"- **最低分:** {min(scores)}",
        f"- **中位数:** {sorted(scores)[len(scores) // 2]}",
        f"- **达标 (≥{threshold}):** {above_threshold}",
        f"- **未达标 (<{threshold}):** {below_threshold}",
        f"- **优良率:** {above_threshold / len(scores) * 100:.1f}%",
        "",
        "## 质量分布",
    ]
    for bucket, count in buckets.items():
        bar = "█" * count if count < 50 else "█" * 50
        lines.append(f"- **{bucket}:** {bar} ({count})")

    # 质量总结
    excellent = buckets["81-100"]
    good = buckets["61-80"]
    poor = buckets["0-20"] + buckets["21-40"]
    lines.extend(
        [
            "",
            "## 质量总结",
            f"- **优秀 (81-100):** {excellent} 个文件",
            f"- **良好 (61-80):** {good} 个文件",
            f"- **较差 (<40):** {poor} 个文件",
        ]
    )
    if avg_score >= 80:
        lines.append("- **评级:** 🟢 整体质量优秀")
    elif avg_score >= 60:
        lines.append("- **评级:** 🟡 整体质量良好，仍有提升空间")
    else:
        lines.append("- **评级:** 🔴 整体质量偏低，建议重新编译低分文件")

    if low_quality:
        lines.extend(["", f"## 未达标文件 (<{threshold})", *low_quality[:50]])

    return "\n".join(lines)


def _get_quality_distribution_df() -> pd.DataFrame:
    """获取质量评分分布 DataFrame"""
    manifests, _, _ = get_manifest_data()
    buckets: dict[str, int] = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
    for m in manifests:
        qs = m.get("quality_score")
        if qs is not None and isinstance(qs, (int, float)):
            s = int(qs)
            if s <= 20:
                buckets["0-20"] += 1
            elif s <= 40:
                buckets["21-40"] += 1
            elif s <= 60:
                buckets["41-60"] += 1
            elif s <= 80:
                buckets["61-80"] += 1
            else:
                buckets["81-100"] += 1
    total = sum(buckets.values())
    if total == 0:
        return EMPTY_QUALITY_DF
    return pd.DataFrame({"分数段": list(buckets.keys()), "文件数": list(buckets.values())})


def _get_low_quality_table() -> list[list[str]]:
    """获取低质量文件列表"""
    manifests, _, _ = get_manifest_data()
    settings = get_settings()
    threshold = settings.min_quality_score
    rows: list[list[str]] = []
    for m in manifests:
        qs = m.get("quality_score")
        if qs is not None and isinstance(qs, (int, float)) and int(qs) < threshold:
            name = m.get("original_filename", m.get("source_file", "unknown"))
            status = m.get("status", "unknown")
            rows.append([m.get("id", ""), name, str(int(qs)), STATUS_LABELS.get(status, status)])
            if len(rows) >= 100:
                break
    return rows


def handle_refresh_quality() -> str:
    """刷新质量仪表盘"""
    try:
        return _get_quality_dashboard()
    except Exception as e:
        # UI 事件处理器顶层守卫
        logger.error(f"获取质量数据失败: {e}")
        return f"**获取质量数据失败:** {e}"


def _handle_recompile_low_quality() -> str:
    """重新编译低质量文件：重置状态为 ingested"""
    try:
        settings = get_settings()
        manifests_dir = settings.workspace / "manifests" / "sources"
        manifests = get_all_manifests(settings.workspace)
        threshold = settings.min_quality_score
        reset_count = 0

        for m in manifests:
            qs = m.get("quality_score")
            status = m.get("status", "")
            if (
                qs is not None
                and isinstance(qs, (int, float))
                and int(qs) < threshold
                and status == "compiled"
            ):
                m["status"] = "ingested"
                m_id = m.get("id", "")
                if m_id:
                    manifest_path = manifests_dir / f"{m_id}.json"
                    if manifest_path.exists():
                        manifest_path.write_text(
                            json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8"
                        )
                        reset_count += 1

        if reset_count == 0:
            return "没有需要重新编译的低质量文件"
        return f"已将 {reset_count} 个低质量文件重置为待编译状态。请在「编译控制」Tab 中点击「开始编译」。"
    except Exception as e:
        # UI 事件处理器顶层守卫
        logger.error(f"重新编译准备失败: {e}")
        return f"**操作失败:** {e}"


def create_quality_tab() -> None:
    """创建质量仪表盘 Tab"""
    with gr.Tab("🎯 质量仪表盘"):
        quality_refresh_btn = gr.Button("🔄 刷新质量数据")
        quality_output = gr.Markdown(value="*点击刷新加载质量数据*")
        quality_chart = gr.BarPlot(
            value=EMPTY_QUALITY_DF.copy(),
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
