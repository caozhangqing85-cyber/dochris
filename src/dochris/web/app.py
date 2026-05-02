"""Gradio Web UI 主文件 — 6 个功能页面"""

from __future__ import annotations

import logging
import time
from collections import Counter
from pathlib import Path
from typing import Any

import gradio as gr  # type: ignore[import-untyped]

from dochris import __version__
from dochris.manifest import get_all_manifests
from dochris.settings import get_settings

logger = logging.getLogger(__name__)


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


def _do_query(query_str: str, top_k: int) -> dict[str, Any]:
    """执行查询"""
    from dochris.phases.phase3_query import query

    return query(query_str, mode="combined", top_k=top_k)


def _format_query_results(result: dict[str, Any]) -> str:
    """格式化查询结果为 Markdown"""
    lines: list[str] = []
    elapsed = result.get("time_seconds", 0)
    lines.append(f"**查询耗时:** {elapsed:.2f}s\n")

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
            lines.append(f"### {i}. {title} (相似度: {score:.3f})")
            if source:
                lines.append(f"**来源:** `{source}`\n")
            if content:
                # 截断过长的内容
                display = content[:500] + "..." if len(content) > 500 else content
                lines.append(f"> {display}\n")

    concepts = result.get("concepts", [])
    if concepts:
        lines.append("## 概念匹配\n")
        for i, c in enumerate(concepts, 1):
            name = c.get("name", c.get("title", ""))
            lines.append(f"{i}. **{name}**")

    if not vector_results and not concepts and not answer:
        lines.append("*未找到相关结果*")

    return "\n".join(lines)


def _get_file_table() -> list[list[str]]:
    """获取文件列表（用于 Dataframe 展示）"""
    manifests, _, _ = _get_manifest_data()
    rows: list[list[str]] = []
    for m in manifests[:200]:  # 限制显示数量
        name = m.get("original_filename", m.get("source_file", "unknown"))
        file_type = m.get("type", "unknown")
        status = m.get("status", "unknown")
        quality = str(m.get("quality_score", "-"))
        manifest_id = m.get("id", "")
        rows.append([manifest_id, name, file_type, status, quality])
    return rows


def _get_system_status() -> str:
    """获取系统状态文本"""
    settings = get_settings()
    manifests, status_counter, type_counter = _get_manifest_data()

    lines = [
        "## 系统信息",
        f"- **版本:** {__version__}",
        f"- **工作区:** `{settings.workspace}`",
        f"- **LLM 模型:** {settings.model}",
        f"- **查询模型:** {settings.query_model}",
        f"- **API Base:** `{settings.api_base}`",
        f"- **API Key:** {'已配置' if settings.api_key else '未配置'}",
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
    for ft, count in type_counter.most_common():
        lines.append(f"- **{ft}:** {count}")

    # 向量数据库状态
    data_dir = settings.data_dir
    chroma_path = data_dir / "chroma.sqlite3"
    if chroma_path.exists():
        size_mb = chroma_path.stat().st_size / (1024 * 1024)
        lines.extend(["", "## 向量数据库", f"- **路径:** `{data_dir}`", f"- **大小:** {size_mb:.1f} MB"])
    else:
        lines.extend(["", "## 向量数据库", "- **状态:** 未初始化"])

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

    # 质量分布
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
# Gradio 事件处理函数
# ============================================================


def handle_query(query_str: str, top_k: int) -> str:
    """处理查询请求"""
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
                import shutil

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


def _get_graph_html() -> str:
    """获取知识图谱 D3.js 可视化 HTML"""
    import json

    from dochris.graph.builder import build_graph

    settings = get_settings()
    graph = build_graph(settings.workspace)
    graph_stats = graph.stats()
    d3_data = graph.to_d3()

    # 限制节点数量以保持性能
    max_nodes = 200
    if len(d3_data["nodes"]) > max_nodes:
        # 按连接数排序，保留最重要的节点
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
            link for link in d3_data["links"] if link["source"] in keep_ids and link["target"] in keep_ids
        ]

    data_json = json.dumps(d3_data, ensure_ascii=False)
    stats_json = json.dumps(graph_stats, ensure_ascii=False, indent=2)

    return _GRAPH_HTML_TEMPLATE.replace("{{GRAPH_DATA}}", data_json).replace(
        "{{GRAPH_STATS}}", stats_json
    )


# D3.js 力导向图 HTML 模板
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

// 箭头标记
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

// 搜索
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


def handle_graph_refresh() -> str:
    """刷新知识图谱"""
    try:
        return _get_graph_html()
    except Exception as e:
        logger.error(f"获取知识图谱失败: {e}")
        return f"<p style='color:red;'>获取知识图谱失败: {e}</p>"


# ============================================================
# Gradio 应用工厂
# ============================================================


def create_web_app() -> gr.Blocks:
    """创建 Gradio Web UI

    Returns:
        gr.Blocks 实例
    """
    with gr.Blocks(title="dochris - 个人知识库") as app:
        gr.Markdown(
            f"# dochris 个人知识库 v{__version__}\n"
            "四阶段流水线: 摄入 → 编译 → 审核 → 分发"
        )

        with gr.Tabs():
            # ── Tab 1: 知识库查询 ──
            with gr.Tab("🔍 知识库查询"):
                with gr.Row():
                    query_input = gr.Textbox(
                        label="查询问题",
                        placeholder="输入关键词或问题...",
                        lines=2,
                        scale=4,
                    )
                    with gr.Column(scale=1):
                        top_k_slider = gr.Slider(
                            minimum=1,
                            maximum=20,
                            value=5,
                            step=1,
                            label="返回结果数量 (top_k)",
                        )
                        query_btn = gr.Button("查询", variant="primary")
                query_output = gr.Markdown(label="查询结果", value="*输入查询内容后点击查询*")
                query_btn.click(
                    fn=handle_query,
                    inputs=[query_input, top_k_slider],
                    outputs=query_output,
                )

            # ── Tab 2: 文件管理 ──
            with gr.Tab("📁 文件管理"):
                with gr.Row():
                    refresh_btn = gr.Button("刷新列表")
                    upload_file = gr.File(
                        label="上传文件（支持拖拽）",
                        file_count="multiple",
                    )
                file_status = gr.Markdown(value="*点击刷新加载数据*")
                file_table = gr.Dataframe(
                    headers=["ID", "文件名", "类型", "状态", "质量分"],
                    label="已摄入文件",
                    interactive=False,
                    wrap=True,
                )
                refresh_btn.click(
                    fn=handle_refresh_files,
                    outputs=[file_table, file_status],
                )
                upload_file.change(
                    fn=handle_upload,
                    inputs=[upload_file],
                    outputs=file_status,
                )

            # ── Tab 3: 编译控制 ──
            with gr.Tab("⚙️ 编译控制"):
                with gr.Row():
                    compile_limit = gr.Slider(
                        minimum=1,
                        maximum=100,
                        value=10,
                        step=1,
                        label="编译数量限制",
                    )
                    compile_btn = gr.Button("开始编译", variant="primary")
                compile_output = gr.Markdown(
                    label="编译结果",
                    value="*设置编译数量后点击开始编译*",
                )
                compile_btn.click(
                    fn=handle_compile,
                    inputs=[compile_limit],
                    outputs=compile_output,
                )

            # ── Tab 4: 系统状态 ──
            with gr.Tab("📊 系统状态"):
                status_refresh_btn = gr.Button("刷新状态")
                status_output = gr.Markdown(value="*点击刷新加载状态*")
                status_refresh_btn.click(
                    fn=handle_refresh_status,
                    outputs=status_output,
                )

            # ── Tab 5: 质量仪表盘 ──
            with gr.Tab("🎯 质量仪表盘"):
                quality_refresh_btn = gr.Button("刷新质量数据")
                quality_output = gr.Markdown(value="*点击刷新加载质量数据*")
                quality_refresh_btn.click(
                    fn=handle_refresh_quality,
                    outputs=quality_output,
                )

            # ── Tab 6: 知识图谱 ──
            with gr.Tab("🕸️ 知识图谱"):
                graph_refresh_btn = gr.Button("加载知识图谱")
                graph_output = gr.HTML(
                    value="<p style='color:#888;text-align:center;padding:40px;'>"
                    "点击「加载知识图谱」按钮开始可视化</p>",
                    label="知识图谱可视化",
                )
                graph_refresh_btn.click(
                    fn=handle_graph_refresh,
                    outputs=graph_output,
                )

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
