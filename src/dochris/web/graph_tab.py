"""知识图谱 Tab — D3.js 可视化与刷新逻辑"""

from __future__ import annotations

import html
import json
import logging

from .utils import get_settings

logger = logging.getLogger(__name__)


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

    for node in d3_data["nodes"]:
        if "label" in node and isinstance(node["label"], str):
            node["label"] = html.escape(node["label"], quote=True)
        if "id" in node and isinstance(node["id"], str):
            node["id"] = html.escape(node["id"], quote=True)
        metadata = node.get("metadata")
        if isinstance(metadata, dict):
            for k, v in metadata.items():
                if isinstance(v, str):
                    metadata[k] = html.escape(v, quote=True)

    data_json = json.dumps(d3_data, ensure_ascii=False).replace("</script", "<\\/script")
    stats_json = json.dumps(graph_stats, ensure_ascii=False, indent=2).replace(
        "</script", "<\\/script"
    )

    return _GRAPH_HTML_TEMPLATE.replace("{{GRAPH_DATA}}", data_json).replace(
        "{{GRAPH_STATS}}", stats_json
    )


def _handle_graph_refresh() -> str:
    """刷新知识图谱"""
    try:
        return _get_graph_html()
    except Exception as e:
        logger.error(f"获取知识图谱失败: {e}")
        return f"<p style='color:red;'>获取知识图谱失败: {e}</p>"
