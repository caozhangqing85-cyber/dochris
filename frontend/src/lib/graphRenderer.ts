import * as d3 from 'd3'
import type { SemanticNode, SemanticEdge } from '@/lib/graphBuilder'
import { NODE_STYLES, EDGE_STYLES, PROVENANCE_STYLES, nodeRadius } from '@/lib/graphBuilder'

type D3Node = SemanticNode & d3.SimulationNodeDatum
type D3Edge = SemanticEdge & d3.SimulationLinkDatum<D3Node>

export interface GraphRendererOptions {
  svg: SVGSVGElement
  container: HTMLDivElement
  nodes: SemanticNode[]
  edges: SemanticEdge[]
  highlightedIds: Set<string>
  onNodeClick: (node: SemanticNode) => void
  onNodeDoubleClick: (node: SemanticNode) => void
  onBackgroundClick: () => void
}

export function createForceGraph(opts: GraphRendererOptions) {
  const { svg: svgEl, container, onNodeClick, onNodeDoubleClick, onBackgroundClick } = opts

  const width = container.clientWidth || 800
  const height = container.clientHeight || 600

  const svg = d3.select(svgEl)
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', [0, 0, width, height])

  // Clear previous content
  svg.selectAll('*').remove()

  // Zoom behavior
  const g = svg.append('g')
  const zoom = d3.zoom<SVGSVGElement, unknown>()
    .scaleExtent([0.2, 5])
    .on('zoom', (event) => {
      g.attr('transform', event.transform.toString())
    })
  svg.call(zoom)

  // Click on background to deselect
  svg.on('click', (event) => {
    if (event.target === svgEl) onBackgroundClick()
  })

  // Prepare data
  const nodes: D3Node[] = opts.nodes.map(n => ({ ...n }))
  const edges: D3Edge[] = opts.edges.map(e => ({
    ...e,
    source: typeof e.source === 'string' ? e.source : (e.source as SemanticNode).id,
    target: typeof e.target === 'string' ? e.target : (e.target as SemanticNode).id,
  }))

  // Force simulation
  const simulation = d3.forceSimulation<D3Node>(nodes)
    .force('link', d3.forceLink<D3Node, D3Edge>(edges)
      .id(d => d.id)
      .distance(d => {
        if (d.relation === 'contains_concept') return 80
        if (d.relation === 'compiled_to') return 100
        return 130
      })
      .strength(d => d.relation === 'same_type' ? 0.1 : 0.4)
    )
    .force('charge', d3.forceManyBody<D3Node>()
      .strength(d => {
        const r = nodeRadius(d)
        return -120 - r * 8
      })
      .distanceMax(400)
    )
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide<D3Node>()
      .radius(d => nodeRadius(d) + 4)
      .strength(0.8)
    )

  // ── Render edges ──
  const linkGroup = g.append('g').attr('class', 'edges')

  const link = linkGroup.selectAll('line')
    .data(edges)
    .join('line')
    .attr('stroke', d => EDGE_STYLES[d.relation]?.color || '#ccc')
    .attr('stroke-width', d => {
      const base = d.relation === 'contains_concept' ? 1.8 : d.relation === 'compiled_to' ? 1.2 : 1
      return base + (d.weight || 0) * 1.5
    })
    .attr('stroke-dasharray', d => EDGE_STYLES[d.relation]?.dash || 'none')
    .attr('stroke-opacity', 0.45)

  // ── Render nodes ──
  const nodeGroup = g.append('g').attr('class', 'nodes')

  const node = nodeGroup.selectAll<SVGGElement, D3Node>('g')
    .data(nodes, d => d.id)
    .join('g')
    .style('cursor', 'pointer')
    .call(d3.drag<SVGGElement, D3Node>()
      .on('start', (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart()
        d.fx = d.x; d.fy = d.y
      })
      .on('drag', (event, d) => {
        d.fx = event.x; d.fy = event.y
      })
      .on('end', (event, d) => {
        if (!event.active) simulation.alphaTarget(0)
        d.fx = null; d.fy = null
      })
    )

  // Node circles — different styles per type + provenance color
  node.append('circle')
    .attr('r', d => nodeRadius(d))
    .attr('fill', d => {
      if (d.provenance && PROVENANCE_STYLES[d.provenance]) {
        return PROVENANCE_STYLES[d.provenance].color
      }
      return NODE_STYLES[d.node_type]?.color || '#a39e98'
    })
    .attr('stroke', d => {
      if (d.node_type === 'concept') return '#1aae39'
      if (d.node_type === 'source') return '#0075de'
      if (d.node_type === 'summary') return '#7c3aed'
      return '#fff'
    })
    .attr('stroke-width', d => d.node_type === 'concept' ? 3 : 2.5)
    .attr('opacity', 0.92)
    .style('filter', 'drop-shadow(0 1px 3px rgba(0,0,0,0.12))')

  // Inner ring for concept nodes (double-ring effect to distinguish from documents)
  node.filter(d => d.node_type === 'concept')
    .append('circle')
    .attr('r', d => nodeRadius(d) - 3)
    .attr('fill', 'none')
    .attr('stroke', 'rgba(255,255,255,0.5)')
    .attr('stroke-width', 1.5)
    .attr('pointer-events', 'none')

  // Node labels (for concept nodes or high-degree nodes)
  node.filter(d => d.node_type === 'concept' || d.degree >= 3)
    .append('text')
    .text(d => d.label.length > 12 ? d.label.slice(0, 12) + '…' : d.label)
    .attr('dy', d => nodeRadius(d) + 14)
    .attr('text-anchor', 'middle')
    .attr('font-size', '11px')
    .attr('font-weight', d => d.node_type === 'concept' ? 600 : 400)
    .attr('fill', 'var(--text-muted)')
    .attr('pointer-events', 'none')

  // ── Tooltip ──
  const tooltip = d3.select(container)
    .append('div')
    .attr('class', 'graph-tooltip')
    .style('position', 'absolute')
    .style('display', 'none')
    .style('padding', '10px 14px')
    .style('background', '#fff')
    .style('border', '1px solid rgba(0,0,0,0.08)')
    .style('border-radius', '8px')
    .style('font-size', '13px')
    .style('font-family', 'var(--font-sans)')
    .style('pointer-events', 'none')
    .style('z-index', '10')
    .style('box-shadow', '0 4px 18px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.04)')

  // ── Interactions ──
  node.on('mouseover', function (event, d) {
    d3.select(this).select('circle')
      .transition().duration(150)
      .attr('r', nodeRadius(d) + 4)
      .attr('stroke-width', 3.5)
      .style('filter', 'drop-shadow(0 2px 6px rgba(0,0,0,0.18))')

    // tooltip 坐标基于 container（offsetX/Y 相对 event.target，对 SVG 内部元素不可靠）
    const rect = container.getBoundingClientRect()
    tooltip.style('display', 'block')
      .html(`<b>${d.label}</b><br><span style="color:#615d59">${NODE_STYLES[d.node_type]?.label || d.node_type}</span>${d.provenance ? ` · <span style="color:${PROVENANCE_STYLES[d.provenance]?.color || '#999'}">${PROVENANCE_STYLES[d.provenance]?.label || d.provenance}</span>` : ''}${d.degree ? ` · ${d.degree} 连接` : ''}${d.conceptData?.sourceCount ? ` · ${d.conceptData.sourceCount} 文档` : ''}`)
      .style('left', (event.clientX - rect.left + 14) + 'px')
      .style('top', (event.clientY - rect.top - 10) + 'px')
  })

  node.on('mouseout', function (_event, d) {
    d3.select(this).select('circle')
      .transition().duration(150)
      .attr('r', nodeRadius(d))
      .attr('stroke-width', 2.5)
      .style('filter', 'drop-shadow(0 1px 2px rgba(0,0,0,0.12))')

    tooltip.style('display', 'none')
  })

  node.on('click', (event, d) => {
    event.stopPropagation()
    onNodeClick(d)
  })

  node.on('dblclick', (event, d) => {
    event.stopPropagation()
    event.preventDefault()
    onNodeDoubleClick(d)
  })

  // ── Tick ──
  simulation.on('tick', () => {
    link
      .attr('x1', d => (d.source as D3Node).x!)
      .attr('y1', d => (d.source as D3Node).y!)
      .attr('x2', d => (d.target as D3Node).x!)
      .attr('y2', d => (d.target as D3Node).y!)

    node.attr('transform', d => `translate(${d.x},${d.y})`)
  })

  // ── Highlight API ──
  function highlight(ids: Set<string>) {
    node.select('circle')
      .transition().duration(200)
      .attr('opacity', d => ids.size === 0 || ids.has(d.id) ? 0.95 : 0.15)

    node.select('text')
      .transition().duration(200)
      .attr('opacity', d => ids.size === 0 || ids.has(d.id) ? 1 : 0.1)

    link
      .transition().duration(200)
      .attr('stroke-opacity', d => {
        if (ids.size === 0) return 0.5
        const s = typeof d.source === 'string' ? d.source : (d.source as D3Node).id
        const t = typeof d.target === 'string' ? d.target : (d.target as D3Node).id
        return ids.has(s) || ids.has(t) ? 0.7 : 0.05
      })
  }

  // ── Focus on node (zoom to it) ──
  function focusNode(nodeId: string) {
    const n = nodes.find(n => n.id === nodeId)
    if (!n || n.x == null || n.y == null) return
    const scale = 1.5
    const transform = d3.zoomIdentity
      .translate(width / 2 - n.x * scale, height / 2 - n.y * scale)
      .scale(scale)
    svg.transition().duration(600).call(zoom.transform, transform)
  }

  // ── Fit all nodes into view ──
  function fitToView() {
    if (nodes.length === 0) return
    const xs = nodes.filter(n => n.x != null).map(n => n.x!)
    const ys = nodes.filter(n => n.y != null).map(n => n.y!)
    if (xs.length === 0) return

    const padding = 60
    const minX = Math.min(...xs) - padding
    const maxX = Math.max(...xs) + padding
    const minY = Math.min(...ys) - padding
    const maxY = Math.max(...ys) + padding

    const graphW = maxX - minX
    const graphH = maxY - minY
    if (graphW <= 0 || graphH <= 0) return

    const scale = Math.min(width / graphW, height / graphH, 2)
    const cx = (minX + maxX) / 2
    const cy = (minY + maxY) / 2
    const transform = d3.zoomIdentity
      .translate(width / 2 - cx * scale, height / 2 - cy * scale)
      .scale(scale)

    svg.transition().duration(600).call(zoom.transform, transform)
  }

  // ── Resize handler ──
  function resize() {
    const w = container.clientWidth || 800
    const h = container.clientHeight || 600
    svg.attr('width', w).attr('height', h).attr('viewBox', [0, 0, w, h])
    simulation.force('center', d3.forceCenter(w / 2, h / 2))
    simulation.alpha(0.3).restart()
  }

  // ── Cleanup ──
  function destroy() {
    simulation.stop()
    // 移除 svg 元素自身的事件监听（zoom/click），避免重建时累积
    svg.on('.zoom', null)
    svg.on('click', null)
    svg.selectAll('*').remove()
    tooltip.remove()
  }

  return { simulation, highlight, focusNode, fitToView, resize, destroy }
}
