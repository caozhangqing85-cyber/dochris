import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Share2, Loader2, Search, X, Filter, Layers,
  ZoomIn, Maximize2, ChevronRight, Tag, FileText, BookOpen,
} from 'lucide-react'
import { getGraph, getManifests, getGraphNode } from '@/lib/api'
import { withMinDelay } from '@/lib/utils'
import type {
  SemanticNode, ViewMode,
} from '@/types'
import {
  buildSemanticGraph, filterGraphByView, searchNodes,
  NODE_STYLES, EDGE_STYLES,
} from '@/lib/graphBuilder'
import type { SemanticGraph } from '@/lib/graphBuilder'
import { createForceGraph } from '@/lib/graphRenderer'
import PageHeader from '@/components/ui/PageHeader'
import EmptyState from '@/components/ui/EmptyState'

const VIEW_OPTIONS: { value: ViewMode; label: string; icon: typeof Tag }[] = [
  { value: 'concept', label: '概念视图', icon: Tag },
  { value: 'document', label: '文档视图', icon: FileText },
  { value: 'mixed', label: '混合视图', icon: Layers },
]

export default function GraphPage() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [graph, setGraph] = useState<SemanticGraph | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('concept')
  const [searchQuery, setSearchQuery] = useState('')
  const [highlightedIds, setHighlightedIds] = useState<Set<string>>(new Set())
  const [selectedNode, setSelectedNode] = useState<SemanticNode | null>(null)
  const [nodeDetail, setNodeDetail] = useState<{
    neighbors: Array<{ id: string; label: string; node_type: string }>
  } | null>(null)
  const [showLegend, setShowLegend] = useState(true)
  const [showFilter, setShowFilter] = useState(false)
  const [filterTypes, setFilterTypes] = useState<Set<string>>(new Set(['concept', 'source', 'summary']))

  const containerRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const rendererRef = useRef<ReturnType<typeof createForceGraph> | null>(null)
  const graphRef = useRef<SemanticGraph | null>(null)

  // Keep graphRef in sync
  useEffect(() => { graphRef.current = graph }, [graph])

  // Load graph data
  const loadGraph = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [graphRes, manifests] = await Promise.all([
        withMinDelay(getGraph()),
        getManifests(),
      ])
      const built = buildSemanticGraph(
        graphRes.data?.nodes || [],
        graphRes.data?.edges || [],
        manifests,
      )
      setGraph(built)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  // Auto-load graph on mount
  useEffect(() => { loadGraph() }, [loadGraph])

  // Handle node click (using ref to avoid stale closure)
  const handleNodeClick = useCallback(async (node: SemanticNode) => {
    setSelectedNode(node)
    setNodeDetail(null)
    const currentGraph = graphRef.current

    try {
      const detail = await getGraphNode(node.id)
      const neighbors = detail.data?.neighbors || []
      setNodeDetail({
        neighbors: neighbors.map(n => ({
          id: n.id, label: n.label, node_type: n.node_type,
        })),
      })
    } catch {
      if (currentGraph) {
        const neighbors = currentGraph.edges
          .filter(e => {
            const s = typeof e.source === 'string' ? e.source : (e.source as SemanticNode).id
            const t = typeof e.target === 'string' ? e.target : (e.target as SemanticNode).id
            return s === node.id || t === node.id
          })
          .map(e => {
            const s = typeof e.source === 'string' ? e.source : (e.source as SemanticNode).id
            const t = typeof e.target === 'string' ? e.target : (e.target as SemanticNode).id
            const neighborId = s === node.id ? t : s
            const neighbor = currentGraph.nodes.find(n => n.id === neighborId)
            return {
              id: neighborId,
              label: neighbor?.label || neighborId,
              node_type: neighbor?.node_type || 'unknown',
            }
          })
        setNodeDetail({ neighbors })
      }
    }

    if (currentGraph) {
      const connectedIds = new Set<string>([node.id])
      currentGraph.edges.forEach(e => {
        const s = typeof e.source === 'string' ? e.source : (e.source as SemanticNode).id
        const t = typeof e.target === 'string' ? e.target : (e.target as SemanticNode).id
        if (s === node.id) connectedIds.add(t)
        if (t === node.id) connectedIds.add(s)
      })
      setHighlightedIds(connectedIds)
      rendererRef.current?.highlight(connectedIds)
    }
  }, [])

  // Handle node double-click (focus/zoom)
  const handleNodeDoubleClick = useCallback((node: SemanticNode) => {
    rendererRef.current?.focusNode(node.id)
  }, [])

  // Apply view filter and render
  useEffect(() => {
    if (!graph || !containerRef.current || !svgRef.current) return

    // Ensure container has measurable dimensions
    const container = containerRef.current
    if (container.clientWidth === 0 || container.clientHeight === 0) return

    // Filter by view mode
    let filtered = filterGraphByView(graph, viewMode)

    // Filter by node types
    const allTypes = new Set(Object.keys(NODE_STYLES))
    if (filterTypes.size < allTypes.size) {
      filtered = {
        ...filtered,
        nodes: filtered.nodes.filter(n => filterTypes.has(n.node_type)),
        edges: filtered.edges.filter(e => {
          const s = typeof e.source === 'string' ? e.source : (e.source as SemanticNode).id
          const t = typeof e.target === 'string' ? e.target : (e.target as SemanticNode).id
          return filtered.nodes.some(n => n.id === s) && filtered.nodes.some(n => n.id === t)
        }),
      }
    }

    // Cleanup previous renderer
    if (rendererRef.current) {
      rendererRef.current.destroy()
      rendererRef.current = null
    }

    if (filtered.nodes.length === 0) return

    const renderer = createForceGraph({
      svg: svgRef.current,
      container: containerRef.current,
      nodes: filtered.nodes,
      edges: filtered.edges,
      highlightedIds: new Set(),
      onNodeClick: handleNodeClick,
      onNodeDoubleClick: handleNodeDoubleClick,
      onBackgroundClick: () => {
        setSelectedNode(null)
        setNodeDetail(null)
        setHighlightedIds(new Set())
        rendererRef.current?.highlight(new Set())
      },
    })
    rendererRef.current = renderer

    // Auto-fit after simulation stabilizes
    setTimeout(() => renderer.fitToView(), 800)

    // Re-apply current highlight state after re-render
    if (highlightedIds.size > 0) {
      renderer.highlight(highlightedIds)
    }

    return () => {
      renderer.destroy()
    }
  }, [graph, viewMode, filterTypes, handleNodeClick, handleNodeDoubleClick])

  // Handle search highlight
  useEffect(() => {
    if (!graph) return
    const ids = searchNodes(graph.nodes, searchQuery)
    setHighlightedIds(ids)
    rendererRef.current?.highlight(ids)
  }, [searchQuery, graph])

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      rendererRef.current?.resize()
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  // Loading state
  if (loading && !graph) {
    return (
      <div className="page-container" style={{ padding: 'var(--space-12) var(--space-10)', maxWidth: '100%', margin: '0 auto', height: '100%', display: 'flex', flexDirection: 'column' }}>
        <PageHeader title="知识图谱" description="概念语义网络 · 基于 Karpathy LLM-Wiki 三层架构" />
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 'var(--radius-lg)', minHeight: '480px', border: '1px solid var(--border-default)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 'var(--space-3)' }}>
            <Loader2 size={28} className="animate-spin" style={{ color: 'var(--color-primary)' }} />
            <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>正在加载知识图谱...</span>
          </div>
        </div>
      </div>
    )
  }

  // Error state with retry
  if (error && !graph) {
    return (
      <div className="page-container" style={{ padding: 'var(--space-12) var(--space-10)', maxWidth: '100%', margin: '0 auto', height: '100%', display: 'flex', flexDirection: 'column' }}>
        <PageHeader title="知识图谱" description="概念语义网络 · 基于 Karpathy LLM-Wiki 三层架构" />
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 'var(--radius-lg)', minHeight: '480px', border: '1px solid var(--status-error-border)', background: 'var(--status-error-bg)' }}>
          <EmptyState icon={<Share2 size={28} />} title="加载失败"
            description={error} />
          <button onClick={loadGraph} style={{ ...primaryBtnStyle(false), marginTop: 'var(--space-4)' }}>
            重试
          </button>
        </div>
      </div>
    )
  }

  // No data state
  if (!graph) {
    return (
      <div className="page-container" style={{ padding: 'var(--space-12) var(--space-10)', maxWidth: '100%', margin: '0 auto', height: '100%', display: 'flex', flexDirection: 'column' }}>
        <PageHeader title="知识图谱" description="概念语义网络 · 基于 Karpathy LLM-Wiki 三层架构"
          actions={
            <button onClick={loadGraph} disabled={loading}
              style={primaryBtnStyle(loading)}>
              <Share2 size={14} />
              加载图谱
            </button>
          }
        />
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 'var(--radius-lg)', minHeight: '480px', border: '1px solid var(--border-default)' }}>
          <EmptyState icon={<Share2 size={28} />} title="概念语义图谱"
            description="加载知识库中的概念关系网络，可视化概念间的语义关联" />
        </div>
      </div>
    )
  }

  return (
    <div className="page-container" style={{ padding: 'var(--space-10) var(--space-10)', maxWidth: '100%', margin: '0 auto', height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <PageHeader title="知识图谱" description={`${graph.stats.conceptNodes} 概念 · ${graph.stats.sourceNodes} 文档 · ${graph.stats.totalEdges} 关系`}
        actions={
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <button onClick={loadGraph} disabled={loading}
              style={ghostBtnStyle(loading)}>
              <Loader2 size={14} className={loading ? 'animate-spin' : ''} />
              刷新
            </button>
          </div>
        }
      />

      {error && (
        <div style={{ borderRadius: '4px', padding: 'var(--space-4)', marginBottom: 'var(--space-4)', fontSize: 'var(--text-sm)', background: 'var(--status-error-bg)', color: 'var(--status-error)' }}>
          {error}
        </div>
      )}

      {graph && (
        <div style={{ flex: 1, display: 'flex', gap: 'var(--space-4)', minHeight: '480px' }}>
          {/* ── Toolbar ── */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', width: '44px', flexShrink: 0 }}>
            {/* View mode switcher */}
            {VIEW_OPTIONS.map(v => (
              <button key={v.value} onClick={() => setViewMode(v.value)} title={v.label}
                style={{
                  padding: '6px', borderRadius: '4px', border: 'none',
                  background: viewMode === v.value ? 'var(--color-primary-bg)' : 'transparent',
                  color: viewMode === v.value ? 'var(--color-primary)' : 'var(--text-dimmed)',
                  cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                <v.icon size={18} />
              </button>
            ))}
            <div style={{ borderTop: '1px solid var(--border-subtle)', margin: '4px 0' }} />
            <button onClick={() => setShowFilter(!showFilter)} title="筛选"
              style={toolBtnStyle(showFilter)}>
              <Filter size={18} />
            </button>
            <button onClick={() => setShowLegend(!showLegend)} title="图例"
              style={toolBtnStyle(showLegend)}>
              <BookOpen size={18} />
            </button>
            <div style={{ borderTop: '1px solid var(--border-subtle)', margin: '4px 0' }} />
            <button onClick={() => rendererRef.current?.fitToView()} title="适配视图"
              style={toolBtnStyle(false)}>
              <Maximize2 size={18} />
            </button>
          </div>

          {/* ── Main graph area ── */}
          <div style={{ flex: 1, position: 'relative', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-default)', overflow: 'hidden', background: 'var(--bg-elevated)' }}>
            {/* Search bar overlay */}
            <div style={{
              position: 'absolute', top: '12px', left: '12px', right: selectedNode ? '340px' : '12px',
              zIndex: 10, maxWidth: '320px',
            }}>
              <div style={{ position: 'relative' }}>
                <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dimmed)' }} />
                <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
                  placeholder="搜索概念或文档..."
                  style={{
                    width: '100%', padding: '6px 10px 6px 30px', borderRadius: '4px',
                    fontSize: 'var(--text-sm)', border: '1px solid var(--border-default)',
                    background: 'rgba(255,255,255,0.95)', color: 'var(--text-primary)',
                    outline: 'none', lineHeight: 1.5,
                    boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
                  }} />
                {searchQuery && (
                  <button onClick={() => setSearchQuery('')} style={{
                    position: 'absolute', right: '6px', top: '50%', transform: 'translateY(-50%)',
                    padding: '2px', border: 'none', background: 'transparent',
                    cursor: 'pointer', color: 'var(--text-dimmed)',
                  }}>
                    <X size={12} />
                  </button>
                )}
              </div>
              {searchQuery && highlightedIds.size > 0 && (
                <div style={{
                  fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)',
                  marginTop: '4px', padding: '0 4px',
                }}>
                  匹配 {highlightedIds.size} 个节点
                </div>
              )}
            </div>

            {/* View mode indicator */}
            <div style={{
              position: 'absolute', top: '12px', right: '12px', zIndex: 10,
              display: 'flex', alignItems: 'center', gap: '2px',
              background: 'rgba(255,255,255,0.95)', borderRadius: '4px',
              padding: '2px', border: '1px solid var(--border-subtle)',
              boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
            }}>
              {VIEW_OPTIONS.map(v => (
                <button key={v.value} onClick={() => setViewMode(v.value)}
                  style={{
                    padding: '4px 10px', borderRadius: '3px', border: 'none',
                    fontSize: 'var(--text-xs)', fontWeight: viewMode === v.value ? 600 : 400,
                    cursor: 'pointer',
                    background: viewMode === v.value ? 'var(--color-primary-bg)' : 'transparent',
                    color: viewMode === v.value ? 'var(--color-primary)' : 'var(--text-dimmed)',
                    whiteSpace: 'nowrap',
                  }}>
                  {v.label}
                </button>
              ))}
            </div>

            {/* Filter panel */}
            {showFilter && (
              <div style={{
                position: 'absolute', top: '52px', left: '12px', zIndex: 10,
                background: 'rgba(255,255,255,0.96)', borderRadius: '4px',
                padding: 'var(--space-3)', border: '1px solid var(--border-subtle)',
                boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                minWidth: '160px',
              }}>
                <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-dimmed)', marginBottom: 'var(--space-2)' }}>
                  节点类型筛选
                </div>
                {Object.entries(NODE_STYLES).map(([type, style]) => (
                  <label key={type} style={{
                    display: 'flex', alignItems: 'center', gap: 'var(--space-2)',
                    fontSize: 'var(--text-sm)', color: 'var(--text-primary)', cursor: 'pointer',
                    padding: '4px 0', fontWeight: 400,
                  }}>
                    <input type="checkbox" checked={filterTypes.has(type)}
                      onChange={() => {
                        const next = new Set(filterTypes)
                        if (next.has(type)) next.delete(type); else next.add(type)
                        setFilterTypes(next)
                      }}
                      style={{ accentColor: style.color }} />
                    <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: style.color }} />
                    {style.label} ({(type === 'concept' ? graph.stats.conceptNodes : type === 'source' ? graph.stats.sourceNodes : graph.stats.summaryNodes) || 0})
                  </label>
                ))}
              </div>
            )}

            {/* Legend */}
            {showLegend && (
              <div style={{
                position: 'absolute', bottom: '12px', left: '12px', zIndex: 10,
                background: 'rgba(255,255,255,0.96)', borderRadius: '4px',
                padding: 'var(--space-3) var(--space-4)',
                border: '1px solid var(--border-subtle)',
                boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                maxWidth: '400px',
              }}>
                <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-dimmed)', marginBottom: 'var(--space-2)' }}>
                  图例 · Karpathy LLM-Wiki 三层架构
                </div>
                {/* Layer indicators */}
                <div style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-2)', flexWrap: 'wrap' }}>
                  {[
                    { label: 'Layer 0: Raw', desc: '源文档', color: '#0075de' },
                    { label: 'Layer 1: Wiki', desc: '概念 + 摘要', color: '#1aae39' },
                    { label: 'Layer 2: Schema', desc: '语义关联', color: '#dd5b00' },
                  ].map(l => (
                    <div key={l.label} style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                      <span style={{ width: '8px', height: '8px', borderRadius: '2px', background: l.color }} />
                      <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 500 }}>{l.desc}</span>
                    </div>
                  ))}
                </div>
                <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 'var(--space-2)' }}>
                  <div style={{ display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap' }}>
                    {/* Node types */}
                    {Object.entries(NODE_STYLES).map(([type, style]) => (
                      <div key={type} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: style.color, border: type === 'concept' ? '2px solid #1aae39' : 'none' }} />
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>{style.label}</span>
                      </div>
                    ))}
                    <span style={{ width: '1px', background: 'var(--border-subtle)' }} />
                    {/* Edge types */}
                    {Object.entries(EDGE_STYLES).map(([type, style]) => (
                      <div key={type} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <span style={{
                          width: '16px', height: '0',
                          borderTop: `2px ${style.dash ? 'dashed' : 'solid'} ${style.color}`,
                        }} />
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>{style.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Stats bar */}
            <div style={{
              position: 'absolute', bottom: '12px', right: '12px', zIndex: 10,
              display: 'flex', gap: 'var(--space-3)',
              background: 'rgba(255,255,255,0.96)', borderRadius: '4px',
              padding: '4px 12px', border: '1px solid var(--border-subtle)',
              boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
            }}>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)' }}>
                节点 {graph.stats.totalNodes}
              </span>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)' }}>
                边 {graph.stats.totalEdges}
              </span>
            </div>

            {/* D3 SVG container */}
            <div ref={containerRef} style={{ width: '100%', height: '100%', position: 'relative', minHeight: '400px' }}>
              <svg ref={svgRef} style={{ width: '100%', height: '100%', display: 'block' }} />
            </div>
          </div>

          {/* ── Detail panel ── */}
          {selectedNode && (
            <div style={{
              width: '320px', flexShrink: 0,
              borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-default)',
              background: 'var(--bg-card)', overflow: 'auto',
              display: 'flex', flexDirection: 'column',
            }}>
              {/* Header */}
              <div style={{
                padding: 'var(--space-4) var(--space-5)',
                borderBottom: '1px solid var(--border-subtle)',
                display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
              }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{
                    fontSize: 'var(--text-base)', fontWeight: 700, color: 'var(--text-primary)',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    letterSpacing: '-0.15px',
                  }}>
                    {selectedNode.label}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginTop: 'var(--space-1)' }}>
                    <span style={{
                      display: 'inline-flex', padding: '1px 6px', borderRadius: 'var(--radius-full)',
                      fontSize: '10px', fontWeight: 600,
                      background: NODE_STYLES[selectedNode.node_type]?.bg,
                      color: NODE_STYLES[selectedNode.node_type]?.color,
                    }}>
                      {NODE_STYLES[selectedNode.node_type]?.label || selectedNode.node_type}
                    </span>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)' }}>
                      {selectedNode.degree} 个连接
                    </span>
                  </div>
                </div>
                <button onClick={() => { setSelectedNode(null); setNodeDetail(null); setHighlightedIds(new Set()); rendererRef.current?.highlight(new Set()) }}
                  style={{ padding: '4px', borderRadius: '4px', border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-dimmed)' }}>
                  <X size={14} />
                </button>
              </div>

              {/* Concept detail */}
              {'conceptData' in selectedNode && (selectedNode as SemanticNode).conceptData && (
                <div style={{ padding: 'var(--space-4) var(--space-5)', borderBottom: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-dimmed)', marginBottom: 'var(--space-2)' }}>
                    概念说明
                  </div>
                  <p style={{ fontSize: 'var(--text-sm)', lineHeight: 'var(--leading-relaxed)', color: 'var(--text-secondary)', margin: 0, fontWeight: 400 }}>
                    {(selectedNode as SemanticNode).conceptData!.explanation || '暂无说明'}
                  </p>
                  <div style={{ marginTop: 'var(--space-3)', fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)' }}>
                    出现在 {(selectedNode as SemanticNode).conceptData!.sourceCount} 个文档中
                  </div>
                </div>
              )}

              {/* Metadata */}
              {selectedNode.metadata && Object.keys(selectedNode.metadata).length > 0 && (
                <div style={{ padding: 'var(--space-4) var(--space-5)', borderBottom: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-dimmed)', marginBottom: 'var(--space-2)' }}>
                    元数据
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {Object.entries(selectedNode.metadata).slice(0, 8).map(([k, v]) => (
                      <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-2)' }}>
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dimmed)' }}>{k}</span>
                        <span style={{
                          fontSize: 'var(--text-xs)', fontWeight: 500, color: 'var(--text-primary)',
                          maxWidth: '60%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textAlign: 'right',
                        }}>{v}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Neighbors */}
              <div style={{ padding: 'var(--space-4) var(--space-5)', flex: 1 }}>
                <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-dimmed)', marginBottom: 'var(--space-3)' }}>
                  关联节点 ({nodeDetail?.neighbors?.length || '...'})
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  {(nodeDetail?.neighbors || []).slice(0, 20).map((n, i) => (
                    <button key={i} onClick={() => {
                      const node = graph.nodes.find(gn => gn.id === n.id)
                      if (node) handleNodeClick(node as SemanticNode)
                    }}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 'var(--space-2)',
                        padding: '6px 8px', borderRadius: '4px', border: 'none',
                        background: 'transparent', cursor: 'pointer', width: '100%', textAlign: 'left',
                      }}
                      onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                      <span style={{
                        width: '7px', height: '7px', borderRadius: '50%', flexShrink: 0,
                        background: NODE_STYLES[n.node_type]?.color || '#a39e98',
                      }} />
                      <span style={{
                        fontSize: 'var(--text-sm)', color: 'var(--text-primary)', fontWeight: 500,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1,
                      }}>
                        {n.label}
                      </span>
                      <span style={{
                        fontSize: '10px', color: 'var(--text-dimmed)', fontWeight: 400, flexShrink: 0,
                      }}>
                        {NODE_STYLES[n.node_type]?.label || n.node_type}
                      </span>
                      <ChevronRight size={12} style={{ color: 'var(--text-dimmed)', flexShrink: 0 }} />
                    </button>
                  ))}
                </div>
              </div>

              {/* Actions */}
              <div style={{
                padding: 'var(--space-3) var(--space-5)',
                borderTop: '1px solid var(--border-subtle)',
                display: 'flex', gap: 'var(--space-2)',
              }}>
                <button onClick={() => handleNodeDoubleClick(selectedNode)}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: '4px',
                    padding: '6px 12px', borderRadius: '4px', border: '1px solid var(--border-default)',
                    background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer',
                    fontSize: 'var(--text-xs)', fontWeight: 500,
                  }}>
                  <ZoomIn size={12} /> 聚焦
                </button>
                <button onClick={() => {
                  setHighlightedIds(new Set())
                  rendererRef.current?.highlight(new Set())
                }}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: '4px',
                    padding: '6px 12px', borderRadius: '4px', border: '1px solid var(--border-default)',
                    background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer',
                    fontSize: 'var(--text-xs)', fontWeight: 500,
                  }}>
                  <Maximize2 size={12} /> 重置视图
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Style helpers ──

function primaryBtnStyle(disabled: boolean): React.CSSProperties {
  return {
    display: 'inline-flex', alignItems: 'center', gap: '6px',
    padding: '8px 16px', borderRadius: '4px', fontSize: '14px', fontWeight: 600,
    color: '#fff', background: 'var(--color-primary)', border: 'none', cursor: 'pointer',
    opacity: disabled ? 0.5 : 1,
  }
}

function ghostBtnStyle(disabled: boolean): React.CSSProperties {
  return {
    display: 'inline-flex', alignItems: 'center', gap: '6px',
    padding: '6px 12px', borderRadius: '4px', fontSize: 'var(--text-sm)',
    border: '1px solid var(--border-default)', background: 'transparent',
    color: 'var(--text-muted)', cursor: 'pointer', fontWeight: 500,
    opacity: disabled ? 0.5 : 1,
  }
}

function toolBtnStyle(active: boolean): React.CSSProperties {
  return {
    padding: '6px', borderRadius: '4px', border: 'none',
    background: active ? 'var(--color-primary-bg)' : 'transparent',
    color: active ? 'var(--color-primary)' : 'var(--text-dimmed)',
    cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
  }
}
