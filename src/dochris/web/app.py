"""Gradio Web UI 主文件 — 6 个功能页面（增强版）"""

from __future__ import annotations

import json
import logging
import platform
import shutil
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import gradio as gr  # type: ignore[import-untyped]
import pandas as pd  # type: ignore[import-untyped]

from dochris import __version__
from dochris.manifest import get_all_manifests
from dochris.settings import get_settings

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────────

_QUERY_MODE_LABELS: dict[str, str] = {
    "combined": "综合查询（推荐）",
    "concept": "概念搜索",
    "summary": "摘要搜索",
    "vector": "向量检索",
    "all": "全量搜索",
}
_STATUS_FILTERS = ["全部", "compiled", "ingested", "failed", "promoted_to_wiki", "promoted"]


# ============================================================
# 数据获取辅助函数
# ============================================================


def _get_manifest_data() -> tuple[list[dict], Counter[str], Counter[str]]:
    """获取 manifest 列表及统计"""
    settings = get_settings()
    manifests = get_all_manifests(settings.workspace)
    status_counter: Counter[str] = Counter(m.get("status", "unknown") for m in manifests)
    type_counter: Counter[str] = Counter(m.get("type", "unknown") for m in manifests)
    return manifests, status_counter, type_counter


def _do_query(query_str: str, top_k: int, mode: str = "combined") -> dict[str, Any]:
    """执行查询"""
    from dochris.phases.phase3_query import query

    return query(query_str, mode=mode, top_k=top_k)


def _format_query_results(result: dict[str, Any]) -> str:
    """格式化查询结果为 Markdown"""
    lines: list[str] = []
    elapsed = result.get("time_seconds", 0)
    mode = result.get("mode", "combined")
    lines.append(
        f"**查询耗时:** {elapsed:.2f}s | **模式:** {_QUERY_MODE_LABELS.get(mode, mode)}\n"
    )

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


def _get_file_table(search: str = "", status_filter: str = "全部") -> list[list[str]]:
    """获取文件列表（用于 Dataframe 展示），支持搜索和过滤"""
    manifests, _, _ = _get_manifest_data()
    rows: list[list[str]] = []
    search_lower = search.lower().strip()

    for m in manifests:
        name = m.get("original_filename", m.get("source_file", "unknown"))
        file_type = m.get("type", "unknown")
        status = m.get("status", "unknown")
        quality = str(m.get("quality_score", "-"))
        manifest_id = m.get("id", "")

        if status_filter != "全部" and status != status_filter:
            continue
        if search_lower and search_lower not in name.lower() and search_lower not in manifest_id.lower() and search_lower not in file_type.lower():
            continue

        rows.append([manifest_id, name, file_type, status, quality])
        if len(rows) >= 200:
            break
    return rows


def _get_system_status() -> str:
    """获取系统状态文本"""
    settings = get_settings()
    manifests, status_counter, type_counter = _get_manifest_data()

    lines = [
        "## 系统信息",
        f"- **版本:** {__version__}",
        f"- **Python:** {platform.python_version()}",
        f"- **平台:** {platform.platform()}",
        f"- **工作区:** `{settings.workspace}`",
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
        lines.append(f"- **磁盘:** {used_gb:.1f}/{total_gb:.1f}GB ({pct:.0f}%) — 剩余 {free_gb:.1f}GB")
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
            ["", "## 向量数据库", f"- **路径:** `{data_dir}`", f"- **大小:** {size_mb:.1f} MB"]
        )
    else:
        lines.extend(["", "## 向量数据库", "- **状态:** 未初始化"])

    lines.extend(["", "## 关键依赖"])
    for pkg in ["gradio", "chromadb", "pandas", "openai"]:
        try:
            mod = __import__(pkg)
            ver = getattr(mod, "__version__", "未知")
            lines.append(f"- **{pkg}:** {ver}")
        except ImportError:
            lines.append(f"- **{pkg}:** 未安装")

    return "\n".join(lines)


def _get_quality_dashboard() -> str:
    """获取质量仪表盘数据"""
    manifests, _, _ = _get_manifest_data()

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
        f"- **达标 (≥{threshold}):** {above_threshold}",
        f"- **未达标 (<{threshold}):** {below_threshold}",
        "",
        "## 质量分布",
    ]
    for bucket, count in buckets.items():
        bar = "█" * count if count < 50 else "█" * 50
        lines.append(f"- **{bucket}:** {bar} ({count})")

    if low_quality:
        lines.extend(["", f"## 未达标文件 (<{threshold})", *low_quality[:50]])

    return "\n".join(lines)


# ============================================================
# 图表数据辅助函数
# ============================================================

_EMPTY_TYPE_DF = pd.DataFrame({"类型": ["暂无数据"], "数量": [0]})
_EMPTY_STATUS_DF = pd.DataFrame({"状态": ["暂无数据"], "数量": [0]})
_EMPTY_QUALITY_DF = pd.DataFrame({"分数段": ["暂无数据"], "文件数": [0]})


def _get_type_distribution_df() -> pd.DataFrame:
    """获取文件类型分布 DataFrame"""
    _, _, type_counter = _get_manifest_data()
    if not type_counter:
        return _EMPTY_TYPE_DF
    return pd.DataFrame(
        {"类型": list(type_counter.keys()), "数量": list(type_counter.values())}
    ).sort_values("数量", ascending=False)


def _get_status_distribution_df() -> pd.DataFrame:
    """获取文件状态分布 DataFrame"""
    _, status_counter, _ = _get_manifest_data()
    if not status_counter:
        return _EMPTY_STATUS_DF
    return pd.DataFrame(
        {"状态": list(status_counter.keys()), "数量": list(status_counter.values())}
    ).sort_values("数量", ascending=False)


def _get_quality_distribution_df() -> pd.DataFrame:
    """获取质量评分分布 DataFrame"""
    manifests, _, _ = _get_manifest_data()
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
        return _EMPTY_QUALITY_DF
    return pd.DataFrame({"分数段": list(buckets.keys()), "文件数": list(buckets.values())})


def _get_low_quality_table() -> list[list[str]]:
    """获取低质量文件列表"""
    manifests, _, _ = _get_manifest_data()
    settings = get_settings()
    threshold = settings.min_quality_score
    rows: list[list[str]] = []
    for m in manifests:
        qs = m.get("quality_score")
        if qs is not None and isinstance(qs, (int, float)) and int(qs) < threshold:
            name = m.get("original_filename", m.get("source_file", "unknown"))
            status = m.get("status", "unknown")
            rows.append([m.get("id", ""), name, str(int(qs)), status])
            if len(rows) >= 100:
                break
    return rows


def _get_compile_info() -> str:
    """获取编译预览信息"""
    manifests, status_counter, _ = _get_manifest_data()
    pending = status_counter.get("ingested", 0)
    compiled = status_counter.get("compiled", 0)
    failed = status_counter.get("failed", 0)
    return (
        f"**待编译:** {pending} | **已编译:** {compiled} | **失败:** {failed}"
        f" | **总计:** {len(manifests)}"
    )


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


def handle_upload(files: list[Any]) -> str:
    """处理文件上传"""
    if not files:
        return "*未选择文件*"
    settings = get_settings()
    raw_dir = settings.raw_dir
    raw_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in files:
        try:
            src = Path(f.name)
            dst = raw_dir / src.name
            if not dst.exists():
                shutil.copy2(src, dst)
                count += 1
        except Exception as e:
            logger.warning(f"上传文件 {f.name} 失败: {e}")
    return f"已上传 {count}/{len(files)} 个文件到 raw/ 目录"


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
        logger.error(f"查询失败: {e}")
        return f"**查询出错:** {e}", history_state, _history_to_table(history_state), None


def _history_to_table(history: list[dict[str, str]]) -> list[list[str]]:
    """将查询历史转换为表格数据"""
    return [
        [h.get("time", ""), h.get("query", ""), h.get("mode", ""), h.get("results", "")]
        for h in history
    ]


def _export_markdown(content: str, prefix: str = "export") -> str | None:
    """将 Markdown 内容导出到临时文件"""
    if not content or content.startswith("*"):
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
        logger.warning(f"导出失败: {e}")
        return None


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
            manifests, status_counter, _ = _get_manifest_data()
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
            if qs is not None and isinstance(qs, (int, float)) and int(qs) < threshold:
                if status == "compiled":
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
        logger.error(f"重新编译准备失败: {e}")
        return f"**操作失败:** {e}"


def _handle_graph_refresh() -> str:
    """刷新知识图谱"""
    try:
        return _get_graph_html()
    except Exception as e:
        logger.error(f"获取知识图谱失败: {e}")
        return f"<p style='color:red;'>获取知识图谱失败: {e}</p>"


# ============================================================
# 知识图谱 D3.js 模板
# ============================================================

_GRAPH_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
  body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #1a1a2e; color: #e0e0e0; }
  .container { display: flex; height: 100vh; }
  .sidebar { width: 280px; padding: 16px; overflow-y: auto; background: #16213e; border-right: 1px solid #0f3460; }
  .sidebar h3 { color: #e94560; margin-top: 0; }
  .stats { font-size: 13px; line-height: 1.6; white-space: pre-wrap; color: #a0a0b0; }
  #search { width: 100%; padding: 8px; border: 1px solid #0f3460; border-radius: 4px; background: #1a1a2e; color: #e0e0e0; margin-bottom: 12px; box-sizing: border-box; }
  #detail { margin-top: 12px; font-size: 13px; color: #c0c0d0; }
  .detail-label { color: #e94560; font-weight: bold; }
  #graph-container { flex: 1; position: relative; }
  svg { width: 100%; height: 100%; }
  .tooltip { position: absolute; padding: 8px 12px; background: rgba(22,33,62,0.95); border: 1px solid #e94560; border-radius: 6px; font-size: 12px; pointer-events: none; color: #e0e0e0; z-index: 10; display: none; }
  .legend { position: absolute; bottom: 16px; left: 16px; background: rgba(22,33,62,0.9); padding: 12px; border-radius: 6px; font-size: 12px; }
  .legend-item { display: flex; align-items: center; gap: 8px; margin: 4px 0; }
  .legend-dot { width: 12px; height: 12px; border-radius: 50%; }
</style>
</head>
<body>
<div class="container">
  <div class="sidebar">
    <h3>🕸️ 知识图谱</h3>
    <input id="search" type="text" placeholder="搜索节点..." />
    <div class="stats" id="stats">{{GRAPH_STATS}}</div>
    <div id="detail"></div>
  </div>
  <div id="graph-container">
    <div class="tooltip" id="tooltip"></div>
    <svg id="graph-svg"></svg>
    <div class="legend">
      <div class="legend-item"><div class="legend-dot" style="background:#4fc3f7"></div>源文件 (source)</div>
      <div class="legend-item"><div class="legend-dot" style="background:#81c784"></div>概念 (concept)</div>
      <div class="legend-item"><div class="legend-dot" style="background:#ffb74d"></div>摘要 (summary)</div>
    </div>
  </div>
</div>
<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const data = {{GRAPH_DATA}};
const colors = { source: '#4fc3f7', concept: '#81c784', summary: '#ffb74d' };
const width = document.getElementById('graph-container').clientWidth;
const height = document.getElementById('graph-container').clientHeight;

const svg = d3.select('#graph-svg').attr('viewBox', [0, 0, width, height]);

svg.append('defs').append('marker')
  .attr('id', 'arrowhead')
  .attr('viewBox', '0 -5 10 10')
  .attr('refX', 20).attr('refY', 0)
  .attr('markerWidth', 6).attr('markerHeight', 6)
  .attr('orient', 'auto')
  .append('path').attr('d', 'M0,-5L10,0L0,5').attr('fill', '#555');

const simulation = d3.forceSimulation(data.nodes)
  .force('link', d3.forceLink(data.links).id(d => d.id).distance(80))
  .force('charge', d3.forceManyBody().strength(-200))
  .force('center', d3.forceCenter(width / 2, height / 2))
  .force('collision', d3.forceCollide().radius(20));

const link = svg.append('g')
  .selectAll('line')
  .data(data.links)
  .join('line')
  .attr('stroke', '#333')
  .attr('stroke-opacity', 0.4)
  .attr('stroke-width', d => Math.max(0.5, d.weight || 1))
  .attr('marker-end', 'url(#arrowhead)');

const node = svg.append('g')
  .selectAll('circle')
  .data(data.nodes)
  .join('circle')
  .attr('r', d => Math.max(4, Math.min(16, (d._degree || 3) * 1.5)))
  .attr('fill', d => colors[d.group] || '#888')
  .attr('stroke', '#222')
  .attr('stroke-width', 1.5)
  .call(d3.drag()
    .on('start', dragstarted)
    .on('drag', dragged)
    .on('end', dragended));

const tooltip = document.getElementById('tooltip');

node.on('mouseover', function(event, d) {
  tooltip.style.display = 'block';
  tooltip.innerHTML = '<b>' + d.label + '</b><br>类型: ' + d.group;
  tooltip.style.left = (event.offsetX + 15) + 'px';
  tooltip.style.top = (event.offsetY - 10) + 'px';
  d3.select(this).attr('stroke', '#e94560').attr('stroke-width', 3);
})
.on('mouseout', function() {
  tooltip.style.display = 'none';
  d3.select(this).attr('stroke', '#222').attr('stroke-width', 1.5);
})
.on('click', function(event, d) {
  const detail = document.getElementById('detail');
  let html = '<p><span class="detail-label">ID:</span> ' + d.id + '</p>';
  html += '<p><span class="detail-label">标签:</span> ' + d.label + '</p>';
  html += '<p><span class="detail-label">类型:</span> ' + d.group + '</p>';
  if (d.metadata) {
    for (const [k, v] of Object.entries(d.metadata)) {
      if (v !== null && v !== undefined) html += '<p><span class="detail-label">' + k + ':</span> ' + v + '</p>';
    }
  }
  detail.innerHTML = html;
});

simulation.on('tick', () => {
  link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
    .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
  node.attr('cx', d => d.x).attr('cy', d => d.y);
});

function dragstarted(event, d) { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; }
function dragged(event, d) { d.fx = event.x; d.fy = event.y; }
function dragended(event, d) { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }

document.getElementById('search').addEventListener('input', function(e) {
  const q = e.target.value.toLowerCase();
  node.attr('opacity', d => !q || d.label.toLowerCase().includes(q) || d.id.toLowerCase().includes(q) ? 1 : 0.15);
  link.attr('stroke-opacity', function(l) {
    const s = l.source, t = l.target;
    const ms = !q || s.label.toLowerCase().includes(q) || s.id.toLowerCase().includes(q);
    const mt = !q || t.label.toLowerCase().includes(q) || t.id.toLowerCase().includes(q);
    return (!q || ms || mt) ? 0.4 : 0.05;
  });
});
</script>
</body>
</html>"""


def _get_graph_html() -> str:
    """获取知识图谱 D3.js 可视化 HTML"""
    from dochris.graph.builder import build_graph

    settings = get_settings()
    graph = build_graph(settings.workspace)
    graph_stats = graph.stats()
    d3_data = graph.to_d3()

    max_nodes = 200
    if len(d3_data["nodes"]) > max_nodes:
        degree: dict[str, int] = {}
        for link in d3_data["links"]:
            degree[link["source"]] = degree.get(link["source"], 0) + 1
            degree[link["target"]] = degree.get(link["target"], 0) + 1
        for n in d3_data["nodes"]:
            n["_degree"] = degree.get(n["id"], 0)
        d3_data["nodes"].sort(key=lambda x: x["_degree"], reverse=True)
        keep_ids = {n["id"] for n in d3_data["nodes"][:max_nodes]}
        d3_data["nodes"] = d3_data["nodes"][:max_nodes]
        d3_data["links"] = [
            link
            for link in d3_data["links"]
            if link["source"] in keep_ids and link["target"] in keep_ids
        ]

    data_json = json.dumps(d3_data, ensure_ascii=False)
    stats_json = json.dumps(graph_stats, ensure_ascii=False, indent=2)

    return _GRAPH_HTML_TEMPLATE.replace("{{GRAPH_DATA}}", data_json).replace(
        "{{GRAPH_STATS}}", stats_json
    )


# ============================================================
# Gradio 应用工厂
# ============================================================


def create_web_app() -> gr.Blocks:
    """创建 Gradio Web UI（增强版）

    Returns:
        gr.Blocks 实例
    """
    with gr.Blocks(
        title="dochris - 个人知识库",
        theme=gr.themes.Soft(),
    ) as app:
        gr.Markdown(
            f"# 📚 dochris 个人知识库 v{__version__}\n"
            "四阶段流水线: 摄入 → 编译 → 审核 → 分发"
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
                            choices=[
                                (label, mode) for mode, label in _QUERY_MODE_LABELS.items()
                            ],
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
                query_output = gr.Markdown(
                    label="查询结果", value="*输入查询内容后点击查询*"
                )

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
                        choices=_STATUS_FILTERS,
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
                    file_status = gr.Markdown(value="*点击筛选或上传文件*", scale=2)

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
                    recompile_btn = gr.Button(
                        "🔄 重置低质量文件为待编译", variant="secondary"
                    )
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
    )
